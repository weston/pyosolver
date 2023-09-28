from pyosolver import node_to_line
from pyosolver import PYOSolver
import os
import pyosolver

PATH = "/mnt/c/PioSOLVER/"
EXECUTABLE = "PioSOLVER2-edge.exe"

DIR = "/mnt/c/Users/wmizu/OneDrive/Desktop/sims"
IN_DIR = "C:\\Users\\wmizu\\OneDrive\\Desktop\\sims"

def main():
		resolve_turn_probes(DIR)

def resolve_turn_probes(directory):
	solver = PYOSolver(PATH, EXECUTABLE)
	for name in os.listdir(directory):
		if not name.endswith(".cfr"):
			continue
		full_path = IN_DIR + "\\" + name
		print(full_path)

		solver.load_tree(full_path)
		solver._run("set_recalc_accuracy", "1 0.1 0.005")
		print('Rebuilding...')
		solver.rebuild_forgotten_streets()
		node = 'r:c:c'
		print('Resolving')
		solver.solve_partial(node)
		solver.wait_for_solver()
		solver.dump_tree(full_path)
		print('done')

main()