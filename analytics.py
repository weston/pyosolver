from pyosolver import node_to_line
from pyosolver import PYOSolver
import pyosolver

PATH = "C:\\PioSOLVER"
EXECUTABLE = "PioSOLVER2-edge"


def simplify_solve(cfr_file_path, position, output_file_name):
	solver = PYOSolver(PATH, EXECUTABLE)
	solver.load_tree(cfr_file_path)
	solver.build_tree()

	# Look at all of the flop sizes available, choose one, try range bets with each.
	tree_info = solver.show_tree_info()
	all_lines = [node_to_line(n) for n in solver.show_all_lines()]
	board = solver.show_node("r")["board"]

	chip_bet_sizes = []
	for child in solver.show_children(get_flop_bet_node(position)):
		if "b" in child["last_action"]:
			chip_bet_sizes.append(int(child["last_action"].replace("b", "")))
		else:
			chip_bet_sizes.append(0)
	
	bet_size_to_ev = {}
	for chips in chip_bet_sizes:
		if chips == 0:
			continue
		for to_remove in chip_bet_sizes:
			if to_remove == chips or to_remove == 0:
				continue
			solver.remove_line(get_cbet_line(position, to_remove))
		if position == "OOP":
			solver.remove_line([0])
		else:
			solver.remove_line([0, 0])
		solver.build_tree()
		solver.go()
		solver.wait_for_solver()
		bet_size_to_ev[chips] = solver.calc_ev(position, "r")
		
		solver.clear_lines()
		# Add lines back
		for line in all_lines:
			solver.add_line(line)

	# Try to check range
	for chips in chip_bet_sizes:
		solver.remove_line(get_cbet_line(position, chips))
	solver.build_tree()
	solver.go()
	solver.wait_for_solver()
	bet_size_to_ev[0] = solver.calc_ev(position, "r")
	solver.clear_lines()
	for line in all_lines:
		solver.add_line(line)
	solver.build_tree()
	
	best_bet_size = 0
	highest_ev = 0
	for bet_size, ev in bet_size_to_ev.items():
		if ev > highest_ev:
			highest_ev = ev
			best_bet_size = bet_size
	chosen_index = chip_bet_sizes.index(best_bet_size)
	cbet_strategy = []
	for i in range(len(chip_bet_sizes)):
		if i == chosen_index:
			cbet_strategy.extend(1326 * [1])
		else:
			cbet_strategy.extend(1326 * [0])

	"""
	Now do turn stuff
	"""
	turn_bet_node = get_turn_bet_node(
		position, 
		best_bet_size, 
		remaining_cards(board)[0],
	)
	
	# Get all turn bet sizes. NODE: These bet sizes are cumulative
	turn_bet_sizes = []
	for i, child in enumerate(solver.show_children(turn_bet_node)):
		if "b" in child["last_action"]:
			bet_size = int(child["last_action"].replace("b", ""))
			turn_bet_sizes.append(bet_size)

	# Run analysis
	turn_strategy = {}
	for turn_bet_size in turn_bet_sizes:
		# Remove all unnecessary flop cbet lines
		for chips in chip_bet_sizes:
			if chips != best_bet_size:
				solver.remove_line(get_cbet_line(position, chips))

		# Remove all unnecessary turn bet lines
		for to_remove in turn_bet_sizes:
			if to_remove == turn_bet_size:
				continue
			solver.remove_line(get_turn_cbet_line(position, best_bet_size, to_remove))

		solver.build_tree()
		solver.go()
		solver.wait_for_solver()

		# Collect data about this run
		for turn_card in remaining_cards(board):
			node = get_turn_bet_node(position, best_bet_size, turn_card)
			ev = solver.calc_ev(position, node)
			if turn_card not in turn_strategy or ev > turn_strategy[turn_card].ev:
				weights = solver.show_strategy(node)
				try:
					assert(len(weights) == 2)
				except Exception:
					print(weights)
					print(node)
					assert False
				turn_strategy[turn_card] = BettingStrategy(
					bet_weights=weights[0],
					check_weights=weights[1],
					ev=ev,
					bet_size_chips=turn_bet_size,
				)

		solver.clear_lines()
		for line in all_lines:
			solver.add_line(line)
		solver.build_tree()

			
	"""
	Lock strategies and dump file
	"""
	solver.set_strategy(get_flop_bet_node(position), *cbet_strategy)
	solver.lock_node(get_flop_bet_node(position))
	for turn_card, strategy in turn_strategy.items():
		node = get_turn_bet_node(position, best_bet_size, turn_card)
		strategy_value = []
		for index, turn_size in enumerate(turn_bet_sizes):
			if turn_size == strategy.bet_size_chips:
				strategy_value.extend(strategy.bet_weights)
			else:
				strategy_value.extend(1326 * [0])
		strategy_value.extend(strategy.check_weights)
		solver.set_strategy(node, *strategy_value)
		solver.lock_node(node)
	
	solver.go()
	solver.wait_for_solver()
	solver.dump_tree(output_file_name)



def get_turn_bet_node(position, flop_bet_chips, turn_card):
	if flop_bet_chips == 0:
		if position == "OOP":
			return "r:0:c:c:{}".format(turn_card)
		else:
			return "r:0:c:c:{}:c".format(turn_card)
	if position == "OOP":
		# bet call turn 
		return "r:0:b{}:c:{}".format(flop_bet_chips, turn_card)
	# Check bet call turn check
	return "r:0:c:b{}:c:{}:c".format(flop_bet_chips, turn_card)
		

def get_flop_bet_node(position):
	if position == "OOP":
		return "r:0"
	return "r:0:c"


def get_cbet_line(position, chip_count):
	if position == "OOP":
		return [chip_count]
	return [0, chip_count]


def get_turn_cbet_line(position, flop_cbet, turn_cbet):
	if position == "OOP":
		return [flop_cbet, flop_cbet, turn_cbet]
	return [0, flop_cbet, flop_cbet, flop_cbet, turn_cbet]


def remaining_cards(board):
	cards = []
	for suit in "cdhs":
		for rank in "A23456789TJQK":
			if rank+suit not in board:
				cards.append(rank+suit)
	return cards


"""
Just a container for betting value, ev, and bet size
"""
class BettingStrategy(object):
	def __init__(self, bet_weights, check_weights, ev, bet_size_chips):
		self.ev = ev
		self.bet_weights = bet_weights.split(" ")
		self.check_weights = check_weights.split(" ")
		self.bet_size_chips = bet_size_chips
