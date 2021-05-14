from pyosolver import node_to_line


def simplify_node(solver, node_id, position):
	"""
	Looks at a single node with multiple bet sizes, and chooses
	a single node that captures the most EV.
	"""
	node_id_without_cards = remove_cards(node_id)
	action_to_lines = {}
	for line in solver.show_all_lines():
		if line.startswith(node_id_without_cards):
			remainder = line.replace(node_id_without_cards, "").split(":")
			if len(remainder) < 2:
				continue
			action = remainder[1]
			if action not in action_to_lines:
				action_to_lines[action] = []
			action_to_lines[action].append(line)

	allowed_action_sets = [["c"]]
	for action in action_to_lines:
		if action != "c":
			allowed_action_sets.append(["c", action])
			allowed_action_sets.append([action])
 
	action_set_to_ev = {
		str(action_to_lines.keys()): solver.calc_ev(position, node_id),
	}
	print(action_set_to_ev)
	return
	for allowed_action_set in allowed_action_sets:
		print(action_set_to_ev)
		lines_to_remove = []
		for action in action_to_lines:
			if action not in allowed_action_set:
				lines_to_remove.extend(action_to_lines[action])
		for line in lines_to_remove:
			solver.remove_line(node_to_line(line))
		solver.solve_partial(node_id)
		action_set_to_ev[str(allowed_action_set)] = solver.calc_ev(
			position, node_id)
		# Solve this node, get EV of node
		# Add lines back	
		for line in lines_to_remove:
			solver.add_line(node_to_line(line))
	return action_set_to_ev


def remove_cards(node_id):
	ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "t", "j", "q", "k", "a"]
	suits = ["c", "d", "h", "s"]
	for suit in suits:
		for rank in ranks:
			if rank+suit in node_id:
				node_id = node_id.replace(rank+suit+":", "")
	print(node_id)
	return node_id