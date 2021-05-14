from pyosolver import PYOSolver
from analytics import simplify_solve

PATH = "C:\\PioSOLVER"
EXECUTABLE = "PioSOLVER2-edge"
def main():
	bet_size_to_ev = simplify_solve("C:\\Users\\wmizu\\Desktop\\weaz.cfr", "IP")
	print("Results")
	for bet_size in sorted(list(bet_size_to_ev.keys())):
		print("Bet Size: {}, EV: {}".format(bet_size, bet_size_to_ev[bet_size]))

main()