from pyosolver import node_to_line
from pyosolver import PYOSolver

PATH = "C:\\PioSOLVER"
EXECUTABLE = "PioSOLVER2-edge"


def simplify_solve(cfr_file_path, position, output_file_name):
	solver = PYOSolver(PATH, EXECUTABLE)
	solver.load_tree(cfr_file_path)
	solver.build_tree()

	# Look at all of the flop sizes available, choose one, try range bets with each.
	tree_info = solver.show_tree_info()
	all_lines = [node_to_line(n) for n in solver.show_all_lines()]

	chip_bet_sizes = []
	for children in solver.show_children(get_flop_bet_node(position)):
		if "b" in children["last_action"]:
			chip_bet_sizes.append(int(children["last_action"].replace("b", "")))
		else:
			chip_bet_sizes.append(0)
	chip_bet_sizes = chip_bet_sizes
	
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
	strategy_values = []
	for i in range(len(chip_bet_sizes)):
		if i == chosen_index:
			strategy_values.extend(1326 * [1])
		else:
			strategy_values.extend(1326 * [0])
	solver.set_strategy(get_flop_bet_node(position), *strategy_values)
	solver.lock_node(get_flop_bet_node(position))
	solver.go()
	solver.wait_for_solver()
	solver.dump_tree(output_file_name)
	print(bet_size_to_ev)
	return bet_size_to_ev


def get_flop_bet_node(position):
	if position == "OOP":
		return "r:0"
	return "r:0:c"

def get_cbet_line(position, chip_count):
	if position == "OOP":
		return [chip_count]
	return [0, chip_count]
