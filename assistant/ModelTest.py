import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from stl import mesh
import numpy as np


# Define different LOD levels (number of vertices to render)
LOD_LEVELS = [1000, 500, 200]  # Example LOD levels

def ExtractVertices(file_path):
    if file_path.endswith(".stl"):
        stl_mesh = mesh.Mesh.from_file(file_path)
        vertices = np.array([tuple(vertex) for vertex in stl_mesh.points], dtype=np.float32)
        return vertices
    else:
        raise ValueError("Unsupported file format. Only .stl files are supported.")

def RenderObject(vertices):
    if vertices is None or len(vertices) == 0:
        return

    glBegin(GL_LINES)
    for vertex_group in vertices:
        if len(vertex_group) % 3 != 0:
            print("Invalid vertex format:", vertex_group)
            continue

        for i in range(0, len(vertex_group), 3):
            vertex = vertex_group[i:i+3]
            glVertex3fv(vertex)
    glEnd()


def main():
    pygame.init()
    display = (800, 600)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)

    stl_filename = r"D:\ALICE\assets\halo_mk_vi_helmet_patched_no_mounting_hole.stl"
    try:
        vertices = ExtractVertices(stl_filename)
    except Exception as e:
        print("Error loading file:", e)
        pygame.quit()
        return

    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glLightfv(GL_LIGHT0, GL_POSITION, (0, 0, 1, 0))
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_DEPTH_TEST)
    glLineWidth(1.0)
    glColor3f(1.0, 1.0, 1.0)

    # Set up isometric perspective projection
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45, (display[0] / display[1]), 0.1, 1000.0)
    glTranslatef(0.0, 0.0, -300)  # Move object further away from the camera
    glRotatef(30, 1, 0, 0)  # Rotate around the x-axis
    glRotatef(180, 0, 1, 0)  # Rotate around the y-axis

    glMatrixMode(GL_MODELVIEW)

    print("Object loaded successfully")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()

        glRotatef(3, 3, 1, 1)  # Rotate by 3 degrees around the axis defined by the vector (3, 1, 1) per frame
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        RenderObject(vertices)
        pygame.display.flip()
        pygame.time.wait(1)

main()
