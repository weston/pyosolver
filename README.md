# PYOSolver.py

PYOSolver.py is a Python wrapper library used for interacting with [PIOSolver](https://www.piosolver.com/). PIOSolver.exe provides a text interface to interact with the solver, and PYOSolver.py allows you to interact with through this interface with Python scripts. This will allow you do more complex scripts than PIOSolver natively supports in the PIOViewer program. Documentation for all of the various commands used to interact with PIOSolver can be found [here](https://piofiles.com/docs/upi_documentation/). This library is specifically intended for PIOSolver 2.0, although there is not reason it wouldn't also support PIOSolver 1.0.


## Usage

```python
>>> from pyosolver import PYOSolver

>>> solver = PYOSolver("C:\\PioSOLVER", "PioSOLVER2-edge")
>>> solver.load_tree("C:\\PioSOLVER\\saves\\AhKs9d.cfr")
>>> solver.show_node("r")
{
    "nodeID": "r",
    "NODE_TYPE": "...",
    "board": ["Ah", "Ks", "9d"],
    "pot": [0, 0, 10],
    "children_no": 1,
    "flags": "...",
}

```
For a more complex example, see [analytics.py](https://github.com/weston/pyosolver/blob/master/analytics.py)
If you have read through the PIOSolver UPI documentation and you still need help understanding how the various PIOSolver commands work, I suggest enabling logs in the PIOSolver settings, doing stuff in PIOSolver and seeing which commands are run. 

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.


## License
lol
