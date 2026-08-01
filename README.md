# PYOSolver.py

PYOSolver.py is a Python wrapper library used for interacting with
[PioSOLVER](https://www.piosolver.com/). PioSOLVER provides a text interface
(UPI) to interact with the solver, and PYOSolver.py lets you drive it from
Python scripts — more complex workflows than PioViewer natively supports.
Documentation for the UPI commands is [here](https://piosolver.com/docs/upi/).

Works with PioSOLVER 2.x and 3.x, including 3.10 (see the 3.10 notes below —
some behaviors changed in ways that silently break older scripts).

## Usage

```python
>>> from pyosolver import PYOSolver

>>> solver = PYOSolver("C:\\PioSOLVER", "PioSOLVER3-edge.exe")
>>> solver.load_tree("C:\\PioSOLVER\\saves\\AhKs9d.cfr")
>>> solver.show_node("r:0")
Node(r:0, OOP_DEC, ('Ah', 'Ks', '9d'), (0, 0, 100), 2, ('PIO_ALG',))
```

For a more complex example, see
[analytics.py](https://github.com/weston/pyosolver/blob/master/analytics.py).
If you have read through the UPI documentation and still need help
understanding how the commands work, enable logs in the PioSOLVER settings, do
stuff in PioViewer and see which commands it runs.

## PioSOLVER 3.10 notes

These were all verified empirically against PioSOLVER-edge 3.10.1; the
wrapper accounts for them, but your scripts need to know:

- **`set_strategy` silently doesn't stick on default trees.** Pio 3's default
  tree algorithm (`v4_small`) derives strategies from regrets, so
  `set_strategy` answers `ok!` but reads, solves, and saves keep the solver's
  own strategy. Before any `set_strategy` / `lock_node` / node-locking
  workflow, convert the tree:

  ```python
  solver.load_tree(path)
  solver.load_all_nodes()
  solver.set_algorithm("original_pio")
  solver.rebuild_tree()          # may need a lot of RAM on big trees
  # now set_strategy / lock_node round-trip exactly
  ```

- **`eliminate_path` + `solve_partial` can crash the solver process** on
  unconverted (`v4_small`) trees. The same `original_pio` conversion makes the
  sequence stable.
- **`rebuild_forgotten_streets` was removed** in 3.10 — use `rebuild_tree()`
  (requires `load_all_nodes()` first). The method is kept for older solvers.
- **Saves are compressed by default since 3.10**, quantizing strategies
  (precision 11). If you need exact frequencies preserved (e.g. after node
  locking), dump with `no_compress`:

  ```python
  solver._run("dump_tree", f'"{path}"', "no_compress")
  ```

- Trees are fast-loaded: many mutating commands error with
  `ERROR: ... incomplete tree` until you call `load_all_nodes()`.
- `set_always_recalc <street> <ms>` — the first argument is a street selector
  (3=flop, 4=turn, 5=river), `0` disables. The wrapper no longer enables it
  at startup: with auto-recalc on, reading a node re-solves it, which
  clobbers strategies you just set.

## Notable wrapper features

- `SolverDied` exception — raised instead of hanging forever when the solver
  process dies mid-command (a dead process otherwise makes `readline()` block
  or spin indefinitely).
- `go(steps, units)` — runs the solver and captures output until it stops;
  returns immediately (with the error text) if the solver rejects the command
  instead of waiting for output that will never come.
- `go_nowait()` — starts solving and returns right after `go ok!`. Pair with
  `stop()` + `wait_for_solver()` for a bounded, version-independent timed
  solve:

  ```python
  solver.set_info_freq(10_000_000)   # quiet progress spam
  solver.go_nowait()
  time.sleep(seconds)
  solver.stop()
  solver.wait_for_solver()
  ```

- `set_algorithm`, `rebuild_tree`, `set_info_freq`, `update_strategy`
  (per-combo strategy edits), `calc_results`, `show_categories`, rake helpers,
  and jesolver output-format support.
- `attach_external_io()` — optional line-bus integration for apps that relay
  solver output elsewhere (capture vs stream modes).

## Contributing

Pull requests are welcome. For major changes, please open an issue first to
discuss what you would like to change.

## License

lol
