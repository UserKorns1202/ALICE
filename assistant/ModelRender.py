import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from stl import mesh

def ExtractVerticesEdges(file_path):
    if file_path.endswith(".stl"):
        # Load the STL file
        stl_mesh = mesh.Mesh.from_file(file_path)

        # Extract vertices and edges
        vertices = {}
        edges = set()
        for face in stl_mesh.vectors:
            for vertex in face:
                vertex_index = tuple(vertex)
                if vertex_index in vertices:
                    vertices[vertex_index] += 1
                else:
                    vertices[vertex_index] = 1

        for face in stl_mesh.vectors:
            for i in range(len(face)):
                vertex1 = tuple(face[i])
                vertex2 = tuple(face[(i + 1) % len(face)])
                if vertices[vertex1] > 1 and vertices[vertex2] > 1:
                    edges.add((vertex1, vertex2))

        return list(vertices.keys()), list(edges)

    elif file_path.endswith(".obj"):
        # Load the OBJ file
        obj = Wavefront(file_path)

        # Extract vertices and edges
        vertices = {}
        edges = set()
        for face in obj.faces:
            for vertex_index in face:
                vertex = obj.vertices[vertex_index]
                vertex_index = tuple(vertex)
                if vertex_index in vertices:
                    vertices[vertex_index] += 1
                else:
                    vertices[vertex_index] = 1

        for face in obj.faces:
            for i in range(len(face)):
                vertex1_index = face[i]
                vertex2_index = face[(i + 1) % len(face)]
                vertex1 = tuple(obj.vertices[vertex1_index])
                vertex2 = tuple(obj.vertices[vertex2_index])
                if vertices[vertex1] > 1 and vertices[vertex2] > 1:
                    edges.add((vertex1, vertex2))

        return list(vertices.keys()), list(edges)

    else:
        raise ValueError("Unsupported file format. Only .stl and .obj files are supported.")


def RenderObject(vertices, edges):
    glBegin(GL_LINES)
    for edge in edges:
        for vertex in edge:
            glVertex3fv(vertex)
    glEnd()



def main():
    pygame.init()
    display = (800, 600)
    pygame.display.set_mode(display, DOUBLEBUF|OPENGL)

    stl_filename = r"D:\ALICE\assets\TROY_COIN.stl"
    try:
        vertices, edges = ExtractVerticesEdges(stl_filename)
    except Exception as e:
        print("Error loading file:", e)
        pygame.quit()
        return

    # Lighting
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glLightfv(GL_LIGHT0, GL_POSITION, (0, 0, 1, 0))

    # Material properties
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    # Depth testing
    glEnable(GL_DEPTH_TEST)

    # Set line width and color
    glLineWidth(1.0)
    glColor3f(1.0, 1.0, 1.0)  # White color

    gluPerspective(45, (display[0]/display[1]), 0.1, 1000.0)
    glTranslatef(0.0, 0.0, -200)  # Move object further away from the camera

    print("Object loaded successfully")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()

        #glRotatef(1, 3, 1, 1)
        #glRotatef(1, 1, 1, 1)  # Rotate around all axes simultaneously
        glRotatef(1, 0, 1, 0)  # Rotate around the y-axis
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        RenderObject(vertices, edges)
        pygame.display.flip()
        pygame.time.wait(10)

main()

