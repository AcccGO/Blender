# 一个字典，包含插件元数据如标题、版本和作者，这些信息会显示在用户设置的插件列表。它还指定了运行该脚本的最低版本要求；更老的版本无法在插件列表中显示该插件。
bl_info = {
    "name": "Wind Vegetation Material Export Addon",
    "author": "Ruofei Zhang",
    "version": (1, 0),
    "blender": (2, 83, 3),
    "description": "Bake pivot and phase ID in vertex color set",
    "warning": "",
    "wiki_url": "",
    "category": "Object",
}

import bpy
import bmesh
import logging
from mathutils import Color, Vector, Matrix
# import model_data
# import command_operators
# import view_panels

import time
from collections import defaultdict


def MakeVertPaths(verts, edges):
    # Initialize the path with all vertices indexes
    result = {v.index: set() for v in verts}
    # Add the possible paths via edges
    for e in edges:
        result[e.vertices[0]].add(e.vertices[1])
        result[e.vertices[1]].add(e.vertices[0])
    return result


def FollowEdges(startingIndex, paths):
    current = [startingIndex]

    follow = True
    while follow:
        # Get indexes that are still in the paths
        eligible = set([ind for ind in current if ind in paths])
        if len(eligible) == 0:
            follow = False  # Stops if no more
        else:
            # Get the corresponding links
            next = [paths[i] for i in eligible]
            # Remove the previous from the paths
            for key in eligible: paths.pop(key)
            # Get the new links as new inputs
            current = set([ind for sub in next for ind in sub])


def CountIslands(obj):
    # Prepare the paths/links from each vertex to others
    paths = MakeVertPaths(obj.data.vertices, obj.data.edges)
    found = True
    n = 0
    while found:
        try:
            # Get one input as long there is one
            startingIndex = next(iter(paths.keys()))
            n = n + 1
            # Deplete the paths dictionary following this starting index
            FollowEdges(startingIndex, paths)
        except:
            found = False
    return n


class ObjectMoveX(bpy.types.Operator):
    """My Object Moving Script"""  # Use this as a tooltip for menu items and buttons.
    bl_idname = "object.move_x"  # Unique identifier for buttons and menu items to reference.
    bl_label = "Move X by One"  # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):  # execute() is called when running the operator.

        # The original script
        scene = context.scene
        for obj in scene.objects:
            obj.location.x += 1.0

        return {'FINISHED'}  # Lets Blender know the operator finished successfully.


class ObjectCursorArray(bpy.types.Operator):
    """Object Cursor Array"""
    bl_idname = "object.cursor_array"
    bl_label = "Cursor Array"
    bl_options = {'REGISTER', 'UNDO'}

    # moved assignment from execute() to the body of the class...
    total: bpy.props.IntProperty(name="Steps", default=2, min=1, max=100)

    def execute(self, context):
        scene = context.scene
        cursor = scene.cursor.location
        obj = context.active_object

        for i in range(self.total):
            obj_new = obj.copy()
            scene.collection.objects.link(obj_new)

            factor = i / self.total
            obj_new.location = (obj.location * factor) + (cursor * (1.0 - factor))

        return {'FINISHED'}


class ObjectPhaseID(bpy.types.Operator):
    """Object Baked Phase ID"""
    bl_idname = "object.baked_phase_id"
    bl_label = "Baked Phase ID"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.app.debug = True

        scene = context.scene
        cursor = scene.cursor.location
        obj = context.object
        mesh = obj.data

        # # 得到分离的mesh数目的一种方法
        # # https://blender.stackexchange.com/questions/75332/how-to-find-the-number-of-loose-parts-with-blenders-python-api
        # print('-------------')
        # start_time = time.time()
        # print('islands: ', CountIslands(obj))
        # elapsed_time = time.time() - start_time
        # print('elapsed_time: ', elapsed_time)
        # print('-------------')

        # raw contains the information in one dimension
        raw = []
        island = []
        visited = []
        face_phase_id = {}

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type="FACE")
        bpy.ops.mesh.select_all(action='DESELECT')

        # Get a BMesh representation
        bm = bmesh.from_edit_mesh(mesh)
        print("bm faces num: ", len(bm.faces))

        for f in bm.faces:
            if f.index not in raw:
                f.select = True

                bpy.ops.mesh.select_linked()
                # bpy.ops.mesh.select_loose()

                # Show the updates in the viewport
                bmesh.update_edit_mesh(mesh, True)

                for fs in bm.faces:
                    if fs.select:
                        island.append(fs.index)
                        raw.append(fs.index)
                        current_phase_id = len(visited)
                        face_phase_id[fs.index] = current_phase_id

                # print("island:", island)
                # print("raw: ", raw)
                bpy.ops.mesh.select_all(action='DESELECT')

                if island not in visited:
                    visited.append(island[:])
                    island.clear()

        print("islands (faces): ", visited)
        print("phase id: ", face_phase_id)
        print("total islands: ", len(visited))

        # # Finish up, write the bmesh back to the mesh
        # bm.to_mesh(mesh)

        bpy.ops.object.mode_set(mode='OBJECT')

        # Get color layer
        name = mesh.name + ": Wind_Pivot_Colorset0"
        if not mesh.vertex_colors or name not in mesh.vertex_colors:
            layer = mesh.vertex_colors.new()
            layer.name = name
        layer = mesh.vertex_colors[name]
        mesh.vertex_colors.active = layer
        vertex_color = layer.data

        i = 0
        total_phase = len(visited)
        for poly in mesh.polygons:
            phase_id_color = face_phase_id[poly.index] * 1.0 / total_phase
            print("phase id color: ", phase_id_color)
            for loop_id in poly.loop_indices:
                vertex_color[i].color = (phase_id_color, 0.0, 0.0, 1.0)
                i += 1

        print("i: ", i)

        # bpy.ops.object.select_all(action='DESELECT')
        # obj.select = True
        # bpy.context.scene.objects.active = obj
        # bpy.ops.mesh.separate(type='LOOSE')
        #
        # # Get a BMesh representation
        # bm = bmesh.new()  # create an empty BMesh
        # bm.from_mesh(me)  # fill it in from a Mesh
        #
        # # Modify the BMesh, can do anything here...
        # for v in bm.verts:
        #     v.co.x += 1.0

        return {'FINISHED'}


# 对obj有用，因为它不会存放层级关系，会把local space下的顶点位置与local_to_world_transform合并
# 对gltf和fbx这样的描述文件，local_space中的顶点位置取决于原点坐标存放，整个模型在世界空间的移动并不影响
# 因此在通常情况下，只需要将mesh pivot origin移动至植物根部
# 但是导出fbx时scale变成了100，场景尺寸原因？
class ObjectPivot(bpy.types.Operator):
    """Object Baked Pivot"""
    bl_idname = "object.baked_pivot"
    bl_label = "Baked Pivot"
    bl_options = {'REGISTER', 'UNDO'}

    # moved assignment from execute() to the body of the class...
    total: bpy.props.IntProperty(name="Steps", default=2, min=1, max=100)

    def execute(self, context):
        scene = context.scene
        cursor = scene.cursor.location

        # Get the active mesh
        obj = context.active_object
        mesh = obj.data
        # print(mesh)

        # Get color layer
        name = mesh.name + ": Wind_Pivot_Colorset1"
        if not mesh.vertex_colors or name not in mesh.vertex_colors:
            layer = mesh.vertex_colors.new()
            layer.name = name
        layer = mesh.vertex_colors[name]
        mesh.vertex_colors.active = layer
        vertex_color = layer.data

        # pivot_v_color = (1,0,0,1)
        pivot_v_color = (obj.location.x, obj.location.y, obj.location.z, 1.0)

        print("vertex_num: ", len(mesh.vertices))
        print("face_num: ", len(mesh.polygons))
        print("color_set_vertex_num: ", len(vertex_color))

        for i in range(len(vertex_color)):
            vertex_color[i].color = pivot_v_color

        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(ObjectMoveX.bl_idname)
    self.layout.operator(ObjectCursorArray.bl_idname)


# 仅在启用插件时运行的函数，这意味着无需激活插件即可加载模块。
def register():
    bpy.utils.register_class(ObjectPivot)
    bpy.utils.register_class(ObjectPhaseID)
    # bpy.types.VIEW3D_MT_object.append(menu_func)
    # bpy.utils.register_module(__name__)
    # command_operators.register()
    # view_panels.register()


# 用于卸载 register 建立的数据的函数，在禁用插件时调用
def unregister():
    bpy.utils.unregister_class(ObjectPivot)
    bpy.utils.unregister_class(ObjectPhaseID)
    # bpy.types.VIEW3D_MT_object.remove(menu_func)
    # bpy.utils.unregister_module(__name__)
    # command_operators.unregister()
    # view_panels.unregister()


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()