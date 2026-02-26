import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np

def load_shape_data(file_path):
    vertices = []
    edges = []

    with open(file_path, 'r') as file:
        for line in file:
            if line.startswith('#'):
                continue  # Skip comment lines
            values = line.strip().split()
            if len(values) == 3:  # Vertex data
                vertices.append([float(val) for val in values])
            elif len(values) == 2:  # Edge connections
                edges.append([int(val) for val in values])
    
    return np.array(vertices), np.array(edges)

def render_shape(vertices, edges):
    glBegin(GL_LINES)
    for edge in edges:
        for vertex_index in edge:
            glVertex3fv(vertices[vertex_index - 1])  # Adjust index to 0-based
    glEnd()

def main():
    pygame.init()
    display = (800, 600)
    pygame.display.set_mode(display, DOUBLEBUF|OPENGL)

    shape_file = r"D:\ALICE\assets\Triforce.txt"
    try:
        vertices, edges = load_shape_data(shape_file)
    except Exception as e:
        print("Error loading shape data:", e)
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

    gluPerspective(45, (display[0]/display[1]), 0.1, 1000.0)
    glTranslatef(0.0, 0.0, -5)  # Move object further away from the camera

    print("Shape data loaded successfully")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            
        #glRotatef(1, 1, 1, 1)  # Rotate around all axes simultaneously
        glRotatef(1, 0, 1, 0)  # Rotate around the y-axis
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        render_shape(vertices, edges)
        pygame.display.flip()
        pygame.time.wait(10)

if __name__ == "__main__":
    main()
