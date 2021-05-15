from pyosolver import PYOSolver
from analytics import simplify_solve
import os


PATH = "C:\\PioSOLVER"
EXECUTABLE = "PioSOLVER2-edge"


def main():
	directory = "C:\\PioSOLVER\\saves\\discovery"
	convert(directory)
	return

	output_file_name = "C:\\Users\\wmizu\\Desktop\\output.cfr"
	bet_size_to_ev = simplify_solve("C:\\Users\\wmizu\\Desktop\\weaz.cfr", "IP", output_file_name)
	print("Results")
	for bet_size in sorted(list(bet_size_to_ev.keys())):
		print("Bet Size: {}, EV: {}".format(bet_size, bet_size_to_ev[bet_size]))


def convert(directory_path):
	for name in os.listdir(directory_path):
		if not name.endswith(".cfr"):
			continue
		full_path = directory_path + "\\" + name
		simplify_solve(full_path, "OOP", directory_path + "\\" + "simplified_" + name)

main()