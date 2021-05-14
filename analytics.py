from pyosolver import node_to_line
from pyosolver import PYOSolver

PATH = "C:\\PioSOLVER"
EXECUTABLE = "PioSOLVER2-edge"
def simplify_solve(cfr_file_path, position):
	solver = PYOSolver(PATH, EXECUTABLE)
	print("Loading tree")
	solver.load_tree(cfr_file_path)
	solver.build_tree()

	# Look at all of the flop sizes available, choose one, try range bets with each.
	tree_info = solver.show_tree_info()
	print("Fetching lines")
	all_lines = [node_to_line(n) for n in solver.show_all_lines()]

	flop_sizes = tree_info["FlopConfig{}.BetSize".format(position)]
	if len(flop_sizes) < 2:
		print("Only one flop size")
		return

	print("Gathering CBet sizes")	
	chip_bet_sizes = []
	for children in solver.show_children(get_flop_bet_node(position)):
		if "b" in children["last_action"]:
			chip_bet_sizes.append(int(children["last_action"].replace("b", "")))
	flop_sizes = sorted(flop_sizes)
	chip_bet_sizes = sorted(chip_bet_sizes)
	
	bet_size_to_ev = {}
	for percent, chips in zip(flop_sizes, chip_bet_sizes):
		for to_remove in chip_bet_sizes:
			if to_remove == chips:
				continue
			solver.remove_line(get_cbet_line(position, to_remove))
		if position == "OOP":
			solver.remove_line([0])
		else:
			solver.remove_line([0, 0])
		solver.build_tree()
		print("Considering range bet for {}%".format(percent))
		solver.go()
		solver.wait_for_solver()
		bet_size_to_ev[percent] = solver.calc_ev(position, "r")
		
		solver.clear_lines()
		# Add lines back
		for line in all_lines:
			solver.add_line(line)

	return bet_size_to_ev


def get_flop_bet_node(position):
	if position == "OOP":
		return "r:0"
	return "r:0:c"

def get_cbet_line(position, chip_count):
	if position == "OOP":
		return [chip_count]
	return [0, chip_count]
