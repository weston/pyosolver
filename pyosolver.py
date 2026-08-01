import subprocess
import os
import queue
from typing import List, Optional, Callable


class SolverDied(Exception):
    """The PioSOLVER process terminated unexpectedly."""


class Node:
    def __init__(self, raw_node_data: str):
        self._raw_node_data = raw_node_data

        items = raw_node_data.strip().split("\n")
        self.node_id = items[0].strip()
        self.last_action = self.node_id.split(":")[-1]
        self.node_type = items[1].strip().split(" ")[0]
        self.board = tuple(items[2].strip().split(" "))
        self.pot = tuple([int(x) for x in items[3].strip().split(" ")])
        self.num_children = int(items[4].strip().split(" ")[0])
        self.flags = tuple(items[5].split(":")[1].strip().split(" "))

    def __repr__(self):
        return f"Node({self.node_id}, {self.node_type}, {self.board}, {self.pot}, {self.num_children}, {self.flags})"

    def __str__(self):
        return self._raw_node_data

    def get_position(self):
        if self.node_type == "OOP_DEC":
            return "OOP"
        elif self.node_type == "IP_DEC":
            return "IP"
        return None


class PYOSolver(object):
    def __init__(
        self,
        path,
        executable_name,
        debug=False,
        log_file=None,
        store_script=False,
        simulate=False,
        end_string="END",
        print_initial_lines=False,
    ):
        self.log_file = log_file
        if log_file is not None:
            self.log_file = open(log_file, "w")
        self.store_script = store_script
        self.commands = []
        self.debug = debug
        self.cfr_file_path = None
        self.solver_path = path
        self.executable_name = executable_name
        self.end_string = end_string
        self.simulate = simulate

        # External IO integration (set later by relayer)
        self._external_line_queue: Optional["queue.Queue[str]"] = None
        self._forward_callback: Optional[Callable[[str], None]] = None
        self._is_paused_fn: Optional[Callable[[], bool]] = None
        self._end_replacement: Optional[str] = None  # what to show instead of END when forwarding

        self.process = subprocess.Popen(
            [os.path.join(self.solver_path, self.executable_name)],
            cwd=self.solver_path,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            encoding="utf8",
        )

        self.jesolver = False
        if ('jesolver' in self.executable_name.lower()):
            self.jesolver = True

        # NOTE: At construction time, the relayer's reader thread usually isn't started yet,
        # so it's safe to read these lines directly here.
        line1 = self.process.stdout.readline()
        line2 = self.process.stdout.readline()
        regstered_to_line = self.process.stdout.readline()
        if print_initial_lines:
            print(line1.strip())
            print(line2.strip())
            print(regstered_to_line.strip())
        self.email = regstered_to_line.replace('registered to ', '').strip()

        self._run("set_end_string", self.end_string)
        self._run("set_threads", "0")
        self._run("set_recalc_accuracy", "0.0025 0.001 0.0005")
        self._run("set_accuracy", "20")
        # NOTE: deliberately no set_always_recalc here. With auto-recalc on,
        # every show_strategy re-solves the node and silently overwrites
        # strategies applied via set_strategy — which breaks node-locking.
        self._run("is_ready")

    # ----- External IO attachment -----
    def attach_external_io(
        self,
        line_queue: "queue.Queue[str]",
        forward_callback: Callable[[str], None],
        is_paused_fn: Callable[[], bool],
        end_replacement: Optional[str] = None,
    ):
        """
        Attach an external line bus and a forwarder. When attached:
          - If is_paused_fn() returns True, commands CAPTURE (return strings).
          - If is_paused_fn() returns False, commands STREAM (forward lines) and return "".

        line_queue: central queue fed by a single reader thread.
        forward_callback: called with each line (with END replaced) when streaming.
        is_paused_fn: tells whether we are currently capturing (paused) or streaming (unpaused).
        end_replacement: what to print instead of the raw END marker when forwarding.
        """
        self._external_line_queue = line_queue
        self._forward_callback = forward_callback
        self._is_paused_fn = is_paused_fn
        self._end_replacement = end_replacement or self.end_string

    # ----- Core helpers -----
    def _readline(self) -> str:
        """
        Read one line from either the external queue (preferred) or the process directly.
        """
        if self._external_line_queue is not None:
            # Block until a line is available (the relayer reader is feeding this)
            return self._external_line_queue.get()
        # Fallback: direct read (standalone usage)
        line = self.process.stdout.readline()
        if line == "" and self.process.poll() is not None:
            raise SolverDied("PioSOLVER process terminated unexpectedly")
        return line

    def _should_capture(self) -> bool:
        # Default to capturing when no external controller is present
        if self._is_paused_fn is None:
            return True
        return self._is_paused_fn()

    def _forward_or_buffer(self, raw_line: str, buffer: list):
        """
        Depending on paused/stream mode, either forward the line or buffer it.
        Always use raw_line to check terminators; when forwarding, replace END visibly.
        """
        if self._should_capture():
            buffer.append(raw_line)
        else:
            # Streaming mode: forward
            if self._forward_callback:
                display_line = raw_line
                if self.end_string and self._end_replacement is not None:
                    display_line = display_line.replace(self.end_string, self._end_replacement)
                self._forward_callback(display_line.rstrip("\n"))

    # ----- Public API -----
    def reset(self):
        self.process = subprocess.Popen(
            [os.path.join(self.solver_path, self.executable_name)],
            cwd=self.solver_path,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            encoding="utf8",
        )

    def is_ready(self):
        return self._run("is_ready")

    def load_tree(self, cfr_file_path):
        self.cfr_file_path = cfr_file_path
        self._run("load_tree", '"' + cfr_file_path + '"')
        self.root_node_info = self.show_node("r:0")
        if self.debug:
            print(f"root_node_info: {self.root_node_info}\n")

    def show_node(self, node_id) -> Optional[Node]:
        data = self._run("show_node", node_id)
        if not data:
            # Streaming mode returns ""; in streaming mode the caller doesn't need parsed output.
            return None
        if "ERROR" in data:
            return None
        return Node(data)

    def set_isomorphism(self, a, b):
        self._run("set_isomorphism", str(a), str(b))

    def calc_results(self):
        data = self._run("calc_results").split("\n")
        return {
            'OOP': float(data[0].split(': ')[1].strip()),
            'IP': float(data[1].split(': ')[1].strip()),
            'exploitable_for': float(data[4].split(': ')[1].strip()),
        }

    def show_children(self, node_id) -> List[Node]:
        """
        Return a list of children of the given specified node.
        """
        data = self._run("show_children", node_id)
        if not data:
            return []
        if "ERROR" in data or data.strip() == "":
            return []

        # Jesolver does not have double newlines in between children nodes
        if self.jesolver:
            data = data.replace('\nchild ', '\n\nchild ')

        children_lines = data.split("\n\n")
        children = []
        for child_line in children_lines:
            items = child_line.split("\n")
            node_data = items[1:]
            child_node = Node("\n".join(node_data))
            children.append(child_node)

        return children

    def show_children_actions(self, node_id) -> Optional[List[str]]:
        data = self._run("show_children", node_id)
        if not data:
            return []
        if "ERROR" in data or data.strip() == "":
            return []
        children_lines = data.split("\n\n")
        return [child.split("\n")[1].strip().split(":")[-1]
                for child in children_lines]

    def show_hand_order(self):
        out = self._run("show_hand_order")
        return out.split(" ") if out else []

    def set_accuracy(self, accuracy: float, accuracy_type: str = "chips"):
        if accuracy_type != "fraction":
            accuracy_type = "chips"
        self._run("set_accuracy", str(accuracy), accuracy_type)

    def set_recalc_accuracy(self, f: float, t: float, r: float):
        self._run("set_recalc_accuracy", str(f), str(t), str(r))

    def go(self, steps=None, units="seconds", quiet=False):
        command = ["go"]
        if steps is not None:
            command += [str(steps), units]
        response = self._run(*command)
        if response and "ERROR" in response:
            # go was rejected (e.g. incomplete tree); no progress lines follow
            return response
        # Stream/capture solver progress lines until the stop trigger
        output = self._get_solver_output(trigger_word="SOLVER: stopped (", quiet=quiet)
        return (response + "\n" + output).strip() if output else response

    def go_nowait(self):
        """Start solving and return immediately (after 'go ok!'). Pair with
        stop() + wait_for_solver(). Unlike go(), never blocks on progress."""
        return self._run("go")

    def stop(self):
        return self._run("stop")

    def wait_for_solver(self):
        return self._run("wait_for_solver")

    def rebuild_forgotten_streets(self):
        return self._run("rebuild_forgotten_streets")

    def rebuild_tree(self):
        # PioSOLVER 3.10+ replacement for rebuild_forgotten_streets
        return self._run("rebuild_tree")

    def set_algorithm(self, name):
        # v4_small (default) derives strategies from regrets, so set_strategy
        # silently doesn't stick. original_pio stores strategies explicitly.
        return self._run("set_algorithm", name)

    def set_info_freq(self, iterations):
        return self._run("set_info_freq", str(iterations))

    def estimate_rebuild_forgotten_streets(self):
        response = self._run("estimate_rebuild_forgotten_streets")
        return response

    def show_tree_info(self):
        data = {}
        raw = self._run("show_tree_info")
        if not raw:
            return data
        for line in raw.split("\n"):
            try:
                _, key, value = line.split("#")
                data[key] = guess_type(key, value)
            except Exception:
                continue
        return data

    def load_all_nodes(self):
        return self._run("load_all_nodes")

    def show_all_lines(self):
        out = self._run("show_all_lines")
        return out.split("\n") if out else []

    def show_effective_stack(self):
        out = self._run("show_effective_stack")
        return int(out.strip()) if out else 0

    def remove_line(self, line):
        line = [str(l) for l in line]
        return self._run("remove_line", " ".join(line))

    def add_line(self, line):
        line = [str(l) for l in line]
        return self._run("add_line", " ".join(line))

    def clear_lines(self):
        return self._run("clear_lines")

    def calc_ev(self, position, node):
        results = self._run("calc_ev", position, node)
        if not results:
            return (), ()
        evs, matchups = results.split("\n")
        evs = tuple(float(ev) for ev in evs.split())
        matchups = tuple(float(matchup) for matchup in matchups.split())
        return evs, matchups

    def solve_partial(self, node_id):
        return self._run("solve_partial", node_id)

    def show_range(self, position, node_id) -> List[float]:
        rng = self._run("show_range", position, node_id)
        if not rng:
            return None
        if "ERROR" in rng:
            print(f"Error in range at {position} {node_id}")
            print(f"{rng}")
            return None
        return [float(freq) for freq in rng.split()]

    def set_range(self, position, *values):
        values = [str(a) for a in values]
        return self._run("set_range", position, *values)

    def set_eff_stack(self, value):
        return self._run("set_eff_stack", str(value))

    def set_pot(self, oop, ip, start):
        return self._run("set_pot", str(oop), str(ip), str(start))

    def set_board(self, board):
        return self._run("set_board", "".join(board))

    def build_tree(self):
        return self._run("build_tree")

    def dump_tree(self, filename, save_type="no_rivers"):
        save_type = save_type.lower().replace("-", "_")
        filename = '"' + filename + '"'
        if save_type in ("small", "no_rivers", None):
            save_type = "no_rivers"
        elif save_type in ("very_small", "no_turns"):
            save_type = "no_turns"
        elif save_type in ("normal", "full"):
            save_type = "full"
        if save_type not in ["no_turns", "no_rivers", "full"]:
            return self._run("dump_tree", filename, "no_rivers")
        if save_type == "full":
            return self._run("dump_tree", filename)
        return self._run("dump_tree", filename, save_type)

    def lock_node(self, node_id):
        return self._run("lock_node", node_id)

    def unlock_node(self, node_id):
        return self._run("unlock_node", node_id)

    def load_script_silent(self, script_filepath):
        return self._run("load_script_silent", script_filepath)

    def set_strategy(self, node_id, *values):
        values = [str(v) for v in values]
        return self._run("set_strategy", node_id, *values)

    def update_strategy(self, node_id, *values):
        self.load_all_nodes()
        self.rebuild_forgotten_streets()
        hand_order = self.show_hand_order() 
        current_strategy = self.show_strategy(node_id);
        current_strategy = [item for sublist in current_strategy for item in sublist]
        for value in values:
            components = value.split(',')
            child_index = int(components[0])
            hand = components[1]
            frequency = float(components[2])
            try:
                current_strategy_index = (child_index * len(hand_order)) + hand_order.index(hand) 
            except Exception:
                current_strategy_index = (child_index * len(hand_order)) + hand_order.index(hand[2:] + hand[:2]) 
            current_strategy[current_strategy_index] = frequency
        assert (self.set_strategy(node_id, *current_strategy) == 'set_strategy ok!')
        return 'update_strategy ok!'

    def show_strategy(self, node_id):
        out = self._run("show_strategy", node_id)
        if not out:
            return []
        strats = out.split("\n")
        return [[float(s) for s in strat.split()] for strat in strats]

    def calc_global_freq(self, node_id: str) -> float:
        out = self._run("calc_global_freq", node_id)
        return float(out) if out else 0.0

    def calc_line_freq(self, node_id: str) -> float:
        out = self._run("calc_line_freq", node_id)
        return float(out) if out else 0.0

    def set_rake(self, fraction: float, cap: int):
        return self._run("set_rake", str(fraction), str(cap))

    def get_rake_fraction_and_cap(self):
        info = self.show_tree_info()
        rake_fraction = float(info.get('Rake.Fraction', 0.0))
        rake_cap = int(info.get('Rake.Cap', 0))
        return rake_fraction, rake_cap

    def show_categories(self, board):
        out = self._run("show_categories", "".join(board))
        if not out:
            return {"made_hands": [], "draws": []}
        made_hands, draws = out.split("\n")
        return {
            "made_hands": [int(a) for a in made_hands.split(' ') if a != ''],
            "draws": [int(a) for a in draws.split(' ') if a != ''],
        }

    def show_category_names(self):
        result = self._run("show_category_names")
        if not result:
            return {"made_hands": [], "draws": []}
        made_hands, draws = result.split("\n")
        return {
            "made_hands": made_hands.split(' '),
            "draws": draws.split(' '),
        }


    def _run(self, *commands):
        if len(commands) == 0:
            return None
        command = commands[0]
        if command == 'update_strategy':
            node = commands[1]
            return self.update_strategy(node, *commands[2:])
        command_with_args = " ".join(commands)
        if self.store_script:
            self.commands.append(command_with_args)

        if self.debug:
            print(command_with_args)
        if self.log_file:
            self.log_file.write(f"[>] {command_with_args}\n")
            self.log_file.flush()

        if self.simulate:
            return ""

        # Send command
        try:
            self.process.stdin.write(" ".join(commands) + "\n")
        except OSError as e:
            raise SolverDied(f"could not write to PioSOLVER: {e}")

        # Normal sentinel
        current_end = f"{self.end_string}\n"

        # Special handling if we're changing the end string right now.
        is_set_end = (command == "set_end_string")
        new_end = None
        if is_set_end and len(commands) >= 2:
            # The solver will start using the NEW token for this response's terminator.
            # To avoid a deadlock, accept BOTH the old and the new for THIS read.
            new_end = f"{commands[1]}\n"

        # Determine trigger word behavior
        trigger_word = None
        if command in NO_OUTPUT_COMMANDS:
            trigger_word = f"{command} ok!\n"

        lines = []

        def is_terminator(line: str) -> bool:
            # For set_end_string, accept either old or new token during this response.
            if is_set_end and new_end is not None:
                return (line == current_end) or (line == new_end)
            return (line == current_end)  # exact line match is the safest

        if trigger_word:
            found_tw = False
            while True:
                line = self._readline()
                # Forward or buffer as usual
                self._forward_or_buffer(line, lines)
                # Trigger seen?
                if (trigger_word in line) or ('ERROR' in line):
                    found_tw = True
                # Now wait until the end marker line
                if found_tw and is_terminator(line):
                    break
        else:
            while True:
                line = self._readline()
                self._forward_or_buffer(line, lines)
                if is_terminator(line):
                    break

        output = "".join(lines)

        if self.log_file:
            self.log_file.write(f"[<] {output}\n")
            self.log_file.flush()

        output = output.replace("END\n", "").strip()  # legacy cleanup; harmless

        # If we just changed the token, commit the new one for future reads.
        if is_set_end and len(commands) >= 2:
            self.end_string = commands[1]

        # In streaming mode, we returned everything via forward_callback; return empty string.
        if not self._should_capture():
            return ""

        return output

    def _get_solver_output(self, trigger_word, quiet=False):
        """
        Used for long-running operations like 'go' which print progress lines.
        Behavior matches _run: capture when paused; forward when streaming.
        """
        current_end = f"{self.end_string}\n"
        lines = []

        # NOTE: We don't change the end string here, but mirror the same matching logic
        # style as in _run (exact line equality to the current end token).
        def is_terminator(line: str) -> bool:
            return (line == current_end)

        if trigger_word:
            while True:
                line = self._readline()
                self._forward_or_buffer(line, lines)
                if trigger_word in line:
                    break
        else:
            while True:
                line = self._readline()
                self._forward_or_buffer(line, lines)
                if is_terminator(line):
                    break

        output = "".join(lines)

        if self.debug:
            print(output)

        if self.log_file:
            self.log_file.write(f"[<] {output}\n")
            self.log_file.flush()

        output = output.replace("END\n", "").strip()
        if not self._should_capture():
            return ""
        return output

    
    def __del__(self):
        if self.log_file:
            self.log_file.close()
        if getattr(self, "process", None):
            try:
                self.process.kill()
            except Exception:
                pass
        if self.store_script:
            with open("script.txt", "w") as f:
                f.write("\n".join(self.commands))


def typed_list(data, t):
    return [t(a) for a in data.split()]


def first_int(to_parse):
    return int(to_parse.split(" ")[0])


def guess_type(key, data_string):
    if "Config" in key and "Size" in key:
        if data_string.find(","):
            try:
                return [int(a) for a in data_string.split(",")]
            except ValueError:
                return data_string.split(",")
        else:
            try:
                return [int(a) for a in data_string.split(" ")]
            except ValueError:
                return data_string.split(" ")
    if "Range" in key:
        return data_string.split(",")
    if "Board" == key:
        return data_string.split(" ")
    return try_value_as_literal(data_string)


def try_value_as_literal(data_string):
    if data_string in ("true", "True"):
        return True
    if data_string in ("false", "False"):
        return False
    try:
        return int(data_string)
    except ValueError:
        pass
    try:
        return float(data_string)
    except ValueError:
        pass
    return data_string


def info_range_to_pio_range(hand_order, info_range):
    hand_class_to_weight = {}
    for blob in info_range:
        if ":" not in blob:
            hand_class = blob
            weight = 1
        else:
            hand_class, weight = blob.split(":")
        hand_class_to_weight[hand_class] = weight
    weights = []
    for specific_hand in hand_order:
        added = False
        for hand_class, weight in hand_class_to_weight.items():
            if is_member(specific_hand, hand_class):
                weights.append(weight)
                added = True
                break
        if not added:
            weights.append(0)
    return weights


def is_member(hand, hand_class):
    if len(hand_class) == 2:
        if hand_class[0] == hand_class[1]:
            return hand[0] == hand[2] == hand_class[0]
        else:
            return (hand[0] == hand_class[0] and hand[2] == hand_class[1]) or (
                hand[0] == hand_class[1] and hand[2] == hand_class[0]
            )
    assert len(hand_class) == 3
    ranks_match = (hand[0] == hand_class[0] and hand[2] == hand_class[1]) or (
        hand[0] == hand_class[1] and hand[2] == hand_class[0]
    )
    if hand_class[2] == "s":
        return ranks_match and hand[1] == hand[3]
    else:
        assert hand_class[2] == "o"
        return ranks_match and hand[1] != hand[3]


NO_OUTPUT_COMMANDS = [
    "is_ready",
    "set_end_string",
    "load_tree",
    "dump_tree",
    "go",
    "stop",
    "wait_for_solver",
    "take_a_break",
    "set_threads",
    "set_info_freq",
    "set_accuracy",
    "set_recalc_accuracy",
    "set_always_recalc",
    "set_isomorphism",
    "set_first_iteration_player",
    "add_preflop_line",
    "remove_preflop_line",
    "clear_preflop_lines",
    "build_preflop_tree",
    "add_to_subset",
    "reset_subset",
    "recover_subset",
    "add_schematic_tree",
    "add_all_flops",
    "set_algorithm",
    "small_strats",
    "add_info_line",
    "reset_tree_info",
    "solve_partial",
    "solve_all_splits",
    "eliminate_path",
    "lock_node",
    "unlock_node",
    "combo_lock_node",
    "set_equal_strats",
    "set_mes",
    "free_tree",
]
