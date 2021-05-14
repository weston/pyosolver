from pyosolver import PYOSolver
from analytics import simplify_node

PATH = "C:\\PioSOLVER"
EXECUTABLE = "PioSOLVER2-edge"
def main():
	solver = PYOSolver(PATH, EXECUTABLE)
	solver.load_tree("C:\\Users\\wmizu\\Desktop\\weaz.cfr")
	simplify_node(solver, "r:0:c:b468:c:2c:c", "IP")

main()