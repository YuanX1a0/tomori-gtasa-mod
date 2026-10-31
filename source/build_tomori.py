import bpy, sys, importlib, os, math
from mathutils import Matrix, Vector, Quaternion

# ---- DragonFF ----
sys.path.insert(0, r"D:/Blender/5.0/scripts/addons")
_m = importlib.import_module("dragonff")
importlib.reload(_m)
_m.register()

BLEND    = r"C:\Users\YuanX1a0\.trae-cn\attachments\701d1b4d-786a-4106-a0ff-f6b56b09996f_7e56b641-f98b-412c-a553-23391c6fd541_企鹅高松灯.blend"
BASE_PED = r"F:\SCRIPS\SAMPSERVER\OSRP\OSRP\models\WM1.dff"
OUT_DIR  = r"F:\SCRIPS\TOMORI_PED"
os.makedirs(OUT_DIR, exist_ok=True)

LOG = []
def log(*a):
    s = " ".join(str(x) for x in a)
    print("###", s)
    LOG.append(s)

# ============================================================
# 1. open source
# ============================================================
bpy.ops.wm.open_mainfile(filepath=BLEND)

for im in bpy.data.images:
    if im.name in ('Render Result', 'Viewer Node'):
        continue
    try:
        im.reload()
        _ = im.pixels[0]
    except Exception as e:
        log("IMG_LOAD_FAIL", im.name, e)
    log("IMG", im.name, "has_data", im.has_data, "size", tuple(im.size))

body_src = bpy.data.objects['mesh0']
head_src = bpy.data.objects['Tomori_mesh']
body_uv = [l.name for l in body_src.data.uv_layers if l.active_render][0]
head_uv = [l.name for l in head_src.data.uv_layers if l.active_render][0]
log("ACTIVE_UV", body_uv, head_uv)
log("SRC", body_src.name, len(body_src.data.vertices), len(body_src.data.polygons),
    head_src.name, len(head_src.data.vertices), len(head_src.data.polygons))

# ============================================================
# 2. bake each object's world transform into its mesh data
# ============================================================
def to_world_mesh(src, name):
    obj = src.copy()
    obj.data = src.data.copy()
    obj.name = name
    obj.data.name = name
    bpy.context.scene.collection.objects.link(obj)
    obj.modifiers.clear()
    # shape keys would override the transformed vertex data when leaving edit
    # mode (they keep their own pre-transform coordinates)
    if obj.data.shape_keys:
        log("SHAPEKEY_CLEAR", name, len(obj.data.shape_keys.key_blocks))
        obj.shape_key_clear()
    mw = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = mw
    bpy.context.view_layer.update()
    obj.data.transform(mw)
    obj.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    obj.data.update()
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    log("TO_WORLD", name, [round(min(p[i] for p in pts), 3) for i in range(3)],
        [round(max(p[i] for p in pts), 3) for i in range(3)])
    return obj

body = to_world_mesh(body_src, "body")
head = to_world_mesh(head_src, "head")

# free the source objects (keep armature for reference, we don't need it)
for o in (body_src, head_src):
    bpy.data.objects.remove(o, do_unlink=True)

# ============================================================
# 3. Blender Z-up  ->  SA ped space (X=up, Y=forward, Z=left)
#    source faces -Y, so ped_y = -blender_y, ped_z = blender_x
#    (x, y, z) -> (z, -y, x)   det = +1  (proper rotation, no mirror)
# ============================================================
M = Matrix(((0, 0, 1, 0),
            (0, -1, 0, 0),
            (1, 0, 0, 0),
            (0, 0, 0, 1)))

pts = []
for o in (body, head):
    pts += [M @ v.co for v in o.data.vertices]
nmin = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
nmax = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
log("MODEL_BOUNDS_PEDSPACE", [round(v, 3) for v in nmin], [round(v, 3) for v in nmax])

# ============================================================
# 4. base ped bounds (height reference)
# ============================================================
before = set(bpy.data.objects)
bpy.ops.import_scene.dff(filepath=BASE_PED)
new_objs = [o for o in bpy.data.objects if o not in before]
arm = [o for o in new_objs if o.type == 'ARMATURE'][0]
base_mesh = [o for o in new_objs if o.type == 'MESH'][0]
bpts = [base_mesh.matrix_world @ v.co for v in base_mesh.data.vertices]
bmin = Vector((min(p.x for p in bpts), min(p.y for p in bpts), min(p.z for p in bpts)))
bmax = Vector((max(p.x for p in bpts), max(p.y for p in bpts), max(p.z for p in bpts)))
log("BASE_BOUNDS", [round(v, 3) for v in bmin], [round(v, 3) for v in bmax])
bpy.data.objects.remove(base_mesh, do_unlink=True)

s = (bmax.x - bmin.x) / (nmax.x - nmin.x)
tx = bmin.x - s * nmin.x
ty = ((bmin.y + bmax.y) / 2) - s * ((nmin.y + nmax.y) / 2)
tz = ((bmin.z + bmax.z) / 2) - s * ((nmin.z + nmax.z) / 2)
T = Matrix.Translation((tx, ty, tz)) @ Matrix.Scale(s, 4)
FULL = T @ M
log("SCALE", round(s, 4), "offset", round(tx, 3), round(ty, 3), round(tz, 3))

for o in (body, head):
    o.data.transform(FULL)
    o.data.update()
bpy.context.view_layer.update()

fp = [v.co for o in (body, head) for v in o.data.vertices]
log("FINAL_BOUNDS", [round(min(p.x for p in fp), 3), round(min(p.y for p in fp), 3), round(min(p.z for p in fp), 3)],
    [round(max(p.x for p in fp), 3), round(max(p.y for p in fp), 3), round(max(p.z for p in fp), 3)])

# ============================================================
# 5. lock every source material to its original UV map
# ============================================================
def add_uvmap_node(obj, uvname):
    for mat in obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        uvnode = nt.nodes.new("ShaderNodeUVMap")
        uvnode.uv_map = uvname
        uvnode.location = (-900, -200)
        for n in nt.nodes:
            if n.type == 'TEX_IMAGE' and not n.inputs['Vector'].is_linked:
                nt.links.new(uvnode.outputs['UV'], n.inputs['Vector'])
        log("UVNODE", obj.name, mat.name, uvname)

add_uvmap_node(body, body_uv)
add_uvmap_node(head, head_uv)

# ============================================================
# 6. join body + head
# ============================================================
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
head.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active
obj.name = "unnamed"
obj.data.name = "unnamed"
me = obj.data
me.update()

def stage_bounds(tag):
    bpy.context.view_layer.update()
    pts = [obj.matrix_world @ v.co for v in me.vertices]
    raw = [v.co for v in me.vertices]
    log("BOUNDS@" + tag, "world", [round(min(p[i] for p in pts), 3) for i in range(3)],
        [round(max(p[i] for p in pts), 3) for i in range(3)],
        "raw", [round(max(p[i] for p in raw), 3) for i in range(3)],
        "mw", [[round(x, 2) for x in r] for r in obj.matrix_world])

stage_bounds("JOIN")
log("JOINED", len(me.vertices), len(me.polygons),
    [m.name if m else None for m in me.materials])

# ============================================================
# 7. remap source rig weights -> SA ped bones
# ============================================================
MAP = {
    'root_x': ' Pelvis',
    'spine_01_x': ' Spine1',
    'neck_x': ' Neck',
    # The anime head is huge and sits low: SA's Head/Neck pivots are near the
    # top of it, so any head/neck animation swings it sideways and it looks
    # crooked.  Keep the head rigid with the torso instead (mascot style).
    'head_x': ' Spine1',
    'shoulder_l': 'Bip01 L Clavicle',
    'arm_stretch_l': ' L UpperArm',
    'forearm_stretch_l': ' L ForeArm',
    'hand_l': ' L Hand',
    'shoulder_r': 'Bip01 R Clavicle',
    'arm_stretch_r': ' R UpperArm',
    'forearm_stretch_r': ' R ForeArm',
    'hand_r': ' R Hand',
    'leftthigh': ' L Thigh',
    'leftfoot': ' L Foot',
    'rightthigh': ' R Thigh',
    'rightfoot': ' R Foot',
}
bone_names = {b.name for b in arm.data.bones}
for src_name, tgt in MAP.items():
    if tgt not in bone_names:
        log("MISSING_BONE", tgt)

old = {g.index: g.name for g in obj.vertex_groups}
per_vertex = []
unmapped = 0
for v in me.vertices:
    acc = {}
    for g in v.groups:
        tgt = MAP.get(old[g.group])
        if tgt is None:
            unmapped += 1
            continue
        acc[tgt] = acc.get(tgt, 0.0) + g.weight
    per_vertex.append(acc)

obj.vertex_groups.clear()
new_groups = {}
for tgt in sorted({t for a in per_vertex for t in a}):
    new_groups[tgt] = obj.vertex_groups.new(name=tgt)

zero_before = sum(1 for a in per_vertex if not a)
for vi, acc in enumerate(per_vertex):
    items = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
    tot = sum(w for _, w in items)
    if tot <= 1e-6:
        continue
    for tgt, w in items:
        new_groups[tgt].add([vi], w / tot, 'REPLACE')
log("WEIGHTS_REMAP", "groups", sorted(new_groups.keys()),
    "unmapped_entries", unmapped, "verts_without_target", zero_before,
    "verts_after", len(me.vertices))
stage_bounds("WEIGHTS")

# ============================================================
# 7.5 pre-pose the flippers so they hang at the body sides
#     The wings were modelled sticking straight out sideways, while the SA
#     rest pose has the arms hanging down at ~65 deg.  Left as-is, the wings
#     stay horizontal in game and the pistol (locked to R Hand) floats in the
#     air.  Rotate each wing around its UpperArm bone head until the wing tip
#     reaches the SA Hand bone head.
# ============================================================
def bone_head(name):
    b = arm.data.bones[name]
    return (arm.matrix_world @ b.head_local).copy()

def smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)

# 1.0 would put the wing tip exactly on the SA hand bone (weapon lines up, but
# the flat wing is pressed into the belly); 0.65 keeps it clear of the body.
WING_SCALE = 0.65

arm_idx = {}
for _side in ('L', 'R'):
    arm_idx[_side] = [obj.vertex_groups[' %s UpperArm' % _side].index,
                      obj.vertex_groups[' %s ForeArm' % _side].index,
                      obj.vertex_groups[' %s Hand' % _side].index]
_all_arm = set(arm_idx['L'] + arm_idx['R'])

# torso half width per height band: does the rotated wing clear the belly?
for _lo, _hi in ((-0.10, 0.15), (0.15, 0.40), (0.40, 0.70)):
    zz = [abs(v.co.z) for v in me.vertices
          if _lo <= v.co.x < _hi and not any(g.group in _all_arm for g in v.groups)]
    if zz:
        log("TORSO_HALFWIDTH", _lo, _hi, round(max(zz), 3))

for side in ('L', 'R'):
    gidx = arm_idx[side]
    pivot = bone_head(' %s UpperArm' % side)
    hand = bone_head(' %s Hand' % side)
    g_hand = gidx[2]
    acc = Vector((0.0, 0.0, 0.0))
    n = 0
    for v in me.vertices:
        w = sum(g.weight for g in v.groups if g.group == g_hand)
        if w >= 0.5:
            acc += v.co
            n += 1
    if n == 0:
        log("WING_SKIP", side)
        continue
    c = acc / n
    q_full = (c - pivot).rotation_difference(hand - pivot)
    # Rotating all the way to the SA hand bone drags the wing flat against the
    # belly (the hand bone is only ~0.47 from the centre line while the belly
    # is ~0.4 wide), so use a fraction of it: the wing then splays out like a
    # fat character's arm instead of sinking into the body.
    q = Quaternion(q_full.axis, q_full.angle * WING_SCALE)
    log("WING_ROT", side, "pivot", [round(x, 3) for x in pivot],
        "tip_now", [round(x, 3) for x in c], "tip_target", [round(x, 3) for x in hand],
        "full_deg", round(math.degrees(q_full.angle), 1),
        "used_deg", round(math.degrees(q.angle), 1))
    for v in me.vertices:
        wa = sum(g.weight for g in v.groups if g.group in gidx)
        if wa <= 0.02:
            continue
        f = min(1.0, wa) * smoothstep(((v.co - pivot).length - 0.02) / 0.20)
        if f <= 0.001:
            continue
        qq = Quaternion((1.0, 0.0, 0.0, 0.0)).slerp(q, f)
        v.co = pivot + qq @ (v.co - pivot)
    me.update()
    acc = Vector((0.0, 0.0, 0.0))
    n = 0
    for v in me.vertices:
        if sum(g.weight for g in v.groups if g.group == g_hand) >= 0.5:
            acc += v.co
            n += 1
    cc = acc / max(1, n)
    log("WING_TIP_AFTER", side, [round(x, 3) for x in cc], "lateral", round(abs(cc.z), 3))

# The droop above rotates the wide flat flipper around a pivot that sits inside
# the belly, so its inner half ends up buried in the torso (up to 0.15m deep).
# Push every wing vertex that is still inside the torso profile back out to the
# surface, so the flipper sits on the belly instead of clipping through it.
PR_STEP = 0.05
PR_MARGIN = 0.06


def torso_radius(x):
    k = int(math.floor(x / PR_STEP))
    best = 0.0
    for kk in (k - 1, k, k + 1):
        best = max(best, _prof.get(kk, 0.0))
    return best


_prof = {}
for v in me.vertices:
    if any(g.group in _all_arm for g in v.groups):
        continue
    _k = int(math.floor(v.co.x / PR_STEP))
    _prof[_k] = max(_prof.get(_k, 0.0), abs(v.co.z))

# Push every vertex that is still inside the torso profile out to the surface,
# and splay the whole flipper further out so it reads as a fat character's arm
# held away from the belly.  Both displacements are then smoothed over the wing
# so the root does not get a hard crease.
WING_OUT = 0.10
for side in ('L', 'R'):
    wing = {}
    for v in me.vertices:
        wa = sum(g.weight for g in v.groups if g.group in arm_idx[side])
        if wa <= 0.02:
            continue
        target = torso_radius(v.co.x) + PR_MARGIN
        d = max(0.0, target - abs(v.co.z)) * min(1.0, wa)
        d += WING_OUT * smoothstep((wa - 0.15) / 0.6)
        wing[v.index] = d
    if not wing:
        log("WING_SKIP", side)
        continue
    adj = dict((i, []) for i in wing)
    for e in me.edges:
        a, b = e.vertices[0], e.vertices[1]
        if a in adj and b in adj:
            adj[a].append(b)
            adj[b].append(a)
    for _ in range(8):
        nxt = {}
        for i, d in wing.items():
            if adj[i]:
                nxt[i] = 0.5 * d + 0.5 * (sum(wing[j] for j in adj[i]) / len(adj[i]))
            else:
                nxt[i] = d
        wing = nxt
    for i, d in wing.items():
        v = me.vertices[i]
        v.co.z += d if v.co.z >= 0.0 else -d
    log("WING_PUSH", side, "verts", len(wing),
        "max", round(max(wing.values()), 3))
me.update()
stage_bounds("WINGPOSE")

# NOTE: parenting/armature modifier is added only after UV/atlas work (see below)

# ============================================================
# 8. bake UV atlas + single material
# ============================================================
bake_uv = me.uv_layers.new(name="BakeUV")
me.uv_layers.active = bake_uv
for l in me.uv_layers:
    l.active_render = (l.name == "BakeUV")

bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.01)
bpy.ops.object.mode_set(mode='OBJECT')
me.update()
log("UNWRAPPED", [u.name for u in me.uv_layers])
stage_bounds("UNWRAP")

img = bpy.data.images.new("tomori", 2048, 2048, alpha=True)
img.generated_color = (0, 0, 0, 1)
for mat in me.materials:
    if not mat or not mat.use_nodes:
        continue
    nt = mat.node_tree
    for n in nt.nodes:
        n.select = False
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.location = (-400, 300)
    tex.select = True
    nt.nodes.active = tex

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 4
bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=16, use_clear=True)
log("BAKED")
stage_bounds("BAKE")
img.scale(1024, 1024)

# ---- brighten the atlas: SA's in-game lighting is much dimmer than the bake
#      preview, and this character's albedo is dark (mean RGB ~110) ----
import numpy as np
buf = np.empty(len(img.pixels), dtype=np.float32)
img.pixels.foreach_get(buf)
buf = buf.reshape(-1, 4)
buf[:, :3] = np.clip((np.clip(buf[:, :3], 0.0, 1.0) ** 0.58) * 1.15, 0.0, 1.0)
buf[:, 3] = np.where(buf[:, 3] > 0.02, 1.0, 0.0)
img.pixels.foreach_set(buf.ravel())
img.update()
log("BRIGHTENED", [round(float(x), 3) for x in buf[buf[:, 3] > 0.5, :3].mean(axis=0)])

img.filepath_raw = os.path.join(OUT_DIR, "tomori_baked.png")
img.file_format = 'PNG'
img.save()
log("BAKE_SAVED", img.filepath_raw, img.size[:])

mat = bpy.data.materials.new("tomori")
mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (300, 0)
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (0, 0)
tex = nt.nodes.new("ShaderNodeTexImage"); tex.location = (-320, 60)
tex.image = img
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
# DFF material colour is taken from the Base Color default value; a grey 0.8
# darkens the texture by 20% in game, so keep it white.
bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
bsdf.inputs["Roughness"].default_value = 0.85
if "Specular IOR Level" in bsdf.inputs:
    bsdf.inputs["Specular IOR Level"].default_value = 0.2
mat.blend_method = 'OPAQUE'

me.materials.clear()
me.materials.append(mat)
for p in me.polygons:
    p.material_index = 0
me.update()
log("MAT_SLOTS", len(me.materials), [m.name for m in me.materials])

# drop every UV layer except the atlas (saves dff space)
for n in [l.name for l in me.uv_layers]:
    if n == "BakeUV":
        continue
    try:
        me.uv_layers.remove(me.uv_layers.get(n))
    except Exception as e:
        log("UV_REMOVE_SKIP", n, e)
try:
    if me.uv_layers.get("BakeUV"):
        me.uv_layers.active = me.uv_layers["BakeUV"]
    for l in me.uv_layers:
        l.active_render = (l.name == "BakeUV")
    me.update()
except Exception as e:
    log("UV_ACTIVE_FAIL", e)
log("UV_FINAL", [u.name for u in me.uv_layers])
stage_bounds("UVREMOVE")

# ---- parent to the SA skeleton (after all mesh-editing steps) ----
obj.parent = arm
obj.matrix_parent_inverse = arm.matrix_world.inverted()
mod = obj.modifiers.new("Armature", 'ARMATURE')
mod.object = arm
log("PARENTED", obj.parent.name, obj.parent_type, "parent_bone", repr(obj.parent_bone))
stage_bounds("PARENT")

# ============================================================
# 9. sanity: no colour attributes, cap 4 influences, coverage
# ============================================================
for a in list(me.attributes):
    if a.data_type in {'FLOAT_COLOR', 'BYTE_COLOR'}:
        me.attributes.remove(a)
log("COLOR_ATTRS", [a.name for a in me.color_attributes])

zero = sum(1 for v in me.vertices if not v.groups or sum(g.weight for g in v.groups) < 1e-4)
max_infl = max(len(v.groups) for v in me.vertices)
log("WEIGHT_CHECK", "verts", len(me.vertices), "zero", zero, "max_infl", max_infl,
    "vgroups", len(obj.vertex_groups))

obj.location = (0, 0, 0)
obj.rotation_euler = (0, 0, 0)
obj.scale = (1, 1, 1)

for o in list(bpy.data.objects):
    if o not in (arm, obj):
        bpy.data.objects.remove(o, do_unlink=True)
log("SCENE_OBJS", [(o.name, o.type) for o in bpy.data.objects])

# ============================================================
# 10. export
# ============================================================
dff_path = os.path.join(OUT_DIR, "tomori.dff")
txd_path = os.path.join(OUT_DIR, "tomori.txd")
bpy.context.view_layer.objects.active = obj
bpy.ops.export_dff.scene(filepath=dff_path)
log("DFF_EXPORTED", dff_path, os.path.getsize(dff_path) if os.path.exists(dff_path) else "MISSING")
bpy.ops.scene.dragonff_txd_export(filepath=txd_path, only_used_textures=True)
log("TXD_EXPORTED", txd_path, os.path.getsize(txd_path) if os.path.exists(txd_path) else "MISSING")

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "tomori_ped.blend"))
log("BLEND_SAVED")

with open(os.path.join(OUT_DIR, "build_log.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(LOG))
print("BUILD_DONE")
