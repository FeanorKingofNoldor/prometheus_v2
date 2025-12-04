extends Node3D
## SceneGraph – minimal 3D visualization for ANT_HILL.
##
## Loads a scene definition from the monitoring backend (`/api/scene/{view_id}`)
## via ApiClient and renders subsystem/database nodes as simple meshes. This is
## intentionally lightweight but gives a real 3D world instead of a pure text
## summary.

@export var view_id: String = "root"

var _nodes_root: Node3D
var _camera: Camera3D

var _cam_yaw: float = 0.0
var _cam_pitch: float = -0.6
var _cam_radius: float = 40.0
var _cam_target: Vector3 = Vector3(30.0, 25.0, 0.0)


func _ready() -> void:
	_nodes_root = Node3D.new()
	_nodes_root.name = "NodesRoot"
	add_child(_nodes_root)

	# Basic camera and light so the scene is visible even if embedded in a
	# SubViewport without additional setup.
	if not has_node("Camera3D"):
		_camera = Camera3D.new()
		_camera.name = "Camera3D"
		add_child(_camera)
		_update_camera_transform()
	else:
		_camera = get_node("Camera3D")

	if not has_node("SunLight"):
		var light: DirectionalLight3D = DirectionalLight3D.new()
		light.name = "SunLight"
		light.rotation_degrees = Vector3(-60.0, 30.0, 0.0)
		add_child(light)

	C2Logger.info("SceneGraph", "Ready for view_id=%s" % view_id)
	await _load_scene()


func _load_scene() -> void:
	C2Logger.info("SceneGraph", "Loading scene for view_id=%s" % view_id)
	var data: Dictionary = await ApiClient.get_scene(view_id)
	if data.has("error"):
		C2Logger.error("SceneGraph", "Backend error for %s: %s" % [view_id, data.get("error")])
		return

	# Clear existing nodes
	for child in _nodes_root.get_children():
		child.queue_free()

	var nodes: Dictionary = data.get("nodes", {})
	var conns: Array = data.get("connections", [])
	C2Logger.info("SceneGraph", "Scene '%s': %d nodes, %d connections" % [view_id, nodes.size(), conns.size()])

	# First create node meshes.
	for id in nodes.keys():
		var n: Dictionary = nodes[id]
		var pos_arr: Array = n.get("pos", [0.0, 0.0, 0.0])
		var pos: Vector3 = Vector3(0.0, 0.0, 0.0)
		if pos_arr is Array and pos_arr.size() >= 3:
			pos = Vector3(float(pos_arr[0]), float(pos_arr[1]), float(pos_arr[2]))
		var label: String = String(n.get("label", id))
		var ntype: String = String(n.get("type", "subsystem"))
		_add_node_mesh(id, label, ntype, pos)

	# Then create simple edge cylinders between nodes (if possible).
	var positions: Dictionary = {}
	for c in _nodes_root.get_children():
		positions[c.name] = c.global_transform.origin

	for conn in conns:
		var src: String = String(conn.get("from", ""))
		var dst: String = String(conn.get("to", ""))
		if not positions.has(src) or not positions.has(dst):
			continue
		_add_edge_mesh(positions[src], positions[dst])


func _add_node_mesh(id: String, label: String, ntype: String, pos: Vector3) -> void:
	var mesh: SphereMesh = SphereMesh.new()
	mesh.radius = 1.5
	mesh.height = 3.0

	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.name = id
	mi.mesh = mesh
	mi.position = pos

	var mat: StandardMaterial3D = StandardMaterial3D.new()
	match ntype:
		"database":
			mat.albedo_color = Color(0.08, 0.78, 0.55)
		"subsystem":
			mat.albedo_color = Color(0.13, 0.67, 0.92)
		_:
			mat.albedo_color = Color(0.73, 0.55, 0.96)
	mi.material_override = mat

	_nodes_root.add_child(mi)

	# Floating label hovering above the node.
	var label_node: Label3D = Label3D.new()
	label_node.text = label
	label_node.position = pos + Vector3(0.0, 1.4, 0.0)
	_nodes_root.add_child(label_node)


func _update_camera_transform() -> void:
	if _camera == null:
		return
	var cp: float = clampf(_cam_pitch, -1.2, -0.1)
	var yaw: float = _cam_yaw
	var r: float = maxf(_cam_radius, 10.0)
	var x: float = _cam_target.x + r * cos(cp) * cos(yaw)
	var y: float = _cam_target.y + r * sin(cp)
	var z: float = _cam_target.z + r * cos(cp) * sin(yaw)
	_camera.position = Vector3(x, y, z)
	_camera.look_at(_cam_target, Vector3.UP)


func _unhandled_input(event: InputEvent) -> void:
	if _camera == null:
		return
	if event is InputEventMouseMotion:
		var mm: InputEventMouseMotion = event as InputEventMouseMotion
		if mm.button_mask & MOUSE_BUTTON_MASK_RIGHT != 0:
			_cam_yaw -= mm.relative.x * 0.01
			_cam_pitch -= mm.relative.y * 0.01
			_update_camera_transform()
	elif event is InputEventMouseButton:
		var mb: InputEventMouseButton = event as InputEventMouseButton
		if not mb.pressed:
			return
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			_cam_radius -= 5.0
			_update_camera_transform()
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_cam_radius += 5.0
			_update_camera_transform()


func _add_edge_mesh(a: Vector3, b: Vector3) -> void:
	var d: float = a.distance_to(b)
	if d <= 0.1:
		return
	var cyl: CylinderMesh = CylinderMesh.new()
	cyl.radius = 0.2
	cyl.height = d

	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.mesh = cyl

	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_color = Color(0.18, 0.32, 0.46)
	mi.material_override = mat

	var mid: Vector3 = (a + b) * 0.5
	mi.global_transform.origin = mid
	var dir: Vector3 = (b - a).normalized()
	# Orient cylinder so its local Y axis points from a to b.
	mi.look_at(mid + dir, Vector3.UP)

	_nodes_root.add_child(mi)
