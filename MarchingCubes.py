import time
import random
import sys
import getopt
import numpy as np
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from noise import snoise4

# Custom debug timer
from debugTimer import debugger



def marchingCubesPolygons(values, threshold):
	"""
	Given 8 values corresponding to corners of a cube and a threshold value,
	this function returns the coordinates of a polygon to be plotted that
	divides the cube along edges where the threshold is crossed.
	inputs:
		values: 8 element array of values at each corner of a unit length
				cube; the order of values should follow the order of the
				local variable VERTICES
		threshold:	the threshold to divide the cube along; the returned
					polygon will divide the cube along this threshold
	"""
	# define vertices of cube in (x,y,z) coordinates
	VERTICES = [
		(0,0,0),
		(1,0,0),
		(1,1,0),
		(0,1,0),
		(0,0,1),
		(1,0,1),
		(1,1,1),
		(0,1,1)]
	# define edges of cube as combination of two vertices
	EDGES = [
		(0,1),
		(1,2),
		(2,3),
		(0,3),
		(0,4),
		(1,5),
		(2,6),
		(3,7),
		(4,5),
		(5,6),
		(6,7),
		(4,7)]

	activeEdges = []		#list of active edges
	polygonVertices = []	#list of vertices to drwa

	# determine which edges are active
	for edge in EDGES:
		#edge is active if it straddles a threshold crossing
		if  ( (values[edge[0]] > threshold) != (values[edge[1]] > threshold) ):
			activeEdges.append(edge)

	# create array of vertices for polygon as midpoints of edges
	for edge in activeEdges:
		midpoint = tuple( (a+b)/2 for a,b in zip(VERTICES[edge[0]], VERTICES[edge[1]]) )
		polygonVertices.append(midpoint)

	# sort array of polygon vertices by distance to one another
	for index in range(len(polygonVertices)):
		a = polygonVertices[index]
		polygonVertices[index+1:] = sorted(polygonVertices[index+1:], 
			key=lambda item: ((item[0]-a[0])**2 + (item[1]-a[1])**2 + (item[2]-a[2])**2)**(1/2)
			)

	return polygonVertices




class MarchingCubesVisualizer : 

	DISPLAYMODE_POINTS = 0
	DISPLAYMODE_MESH = 1
	DISPLAYMODE_WIREFRAME = 2
	
	def __init__(self, screenWidth=800, screenHeight=600, worldSize = 10, debug=True, radius=20):
		# seed random number generator
		random.seed(time.process_time())	
		self.FPS = 30	
		self.seedWorldTimer = self.FPS
		self.displayMode = self.DISPLAYMODE_POINTS
		
		# create initial random world
		self.worldSize = int(worldSize+1)
		self.world = [[[0 for x in range(self.worldSize)] for y in range(self.worldSize)] for z in range(self.worldSize)]
		self.worldThreshold = 0.5
		self.calculateWorldValues()	
		
		#perform initial marching cubes
		self.polygons = [[[[] for x in range(self.worldSize)] for y in range(self.worldSize)] for z in range(self.worldSize)]
		self.findPolygons()
		
		# create openGL window
		pygame.init()
		pygame.display.set_caption('Marching Cubes Visualizer')
		self.displaySize = (screenWidth, screenHeight)
		pygame.display.set_mode(self.displaySize, DOUBLEBUF | OPENGL)
		self.clock = pygame.time.Clock()
		
		# sphere quadric for point mode
		self.sphere = gluNewQuadric()
		
		# configure openGL perspective
		glMatrixMode(GL_PROJECTION)
		gluPerspective(45, (screenWidth/screenHeight), 0.1, 50.0)
		
		# configure model view
		glMatrixMode(GL_MODELVIEW)
		glEnable(GL_CULL_FACE)		#enable culling
		glCullFace(GL_BACK)
		glEnable(GL_DEPTH_TEST)		#enable depth test

		# initial camera setup 
		self.cameraPolar = [radius, 0, 90]	#(r, theta, phi)
		self.polarCameraToCartesian()
		self.cameraTarget = [0, 0, 0]
		self.up = [0, 1, 0]
		glLoadIdentity()
		gluLookAt(*self.cameraPosition, *self.cameraTarget, *self.up)
		
		# optional debug timer
		if debug:
			self.debug = True
			self.debugger = debugger()
		else:
			self.debug = False



	def mainLoop(self):
		"""
		Main loop of Marching Cubes Visualization program.
		Called once per frame until the user closes the opened pygame wndow.
		"""
		while True:
			# cap FPS at 30
			self.dt = self.clock.tick(self.FPS)
			if self.debug:
				self.debugger.log('start')

			# pygame event loop for quit and mouse scrollwheel
			for event in pygame.event.get():
				#handle quit event
				if event.type == pygame.QUIT:
					pygame.quit()
					sys.exit()
				# handle mouse scrollwheel (adjust threshold)
				if event.type == pygame.MOUSEBUTTONDOWN:
					if event.button == 5: 
						self.worldThreshold += 0.01
						if self.worldThreshold > 1.0: self.worldThreshold = 1
					if event.button == 4: 
						self.worldThreshold -= 0.01
						if self.worldThreshold < 0.0: self.worldThreshold = 0
					# reperform marchingCubes if threshold changed
					self.findPolygons()
					if self.debug:
						self.debugger.log('marchingCubes')
			
			# handle camera controller
			self.keyboardController()
			if self.debug:
				self.debugger.log('keyboardController')
			
			#clear last frame's scene and draw new scene
			glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
			self.drawScene()
			if self.debug:
				self.debugger.log('drawScene')
			
			#look at and render scene
			glLoadIdentity()
			gluLookAt(*self.cameraPosition, *self.cameraTarget, *self.up)
			pygame.display.flip()
			if self.debug:
				self.debugger.log('renderScene')
				self.debugger.report()	#print debugger report


	def polarCameraToCartesian(self):
		"""
		Converts the camera's polar position to cartesian and store the result in self.cameraPosition
		"""
		x = self.cameraPolar[0]*np.sin(self.cameraPolar[1]*np.pi/180)*np.sin(self.cameraPolar[2]*np.pi/180)
		y = self.cameraPolar[0]*np.cos(self.cameraPolar[2]*np.pi/180)
		z = self.cameraPolar[0]*np.cos(self.cameraPolar[1]*np.pi/180)*np.sin(self.cameraPolar[2]*np.pi/180)
		self.cameraPosition = [x, y, z]


	def keyboardController(self):
		"""
		Processes user inputs from the keyboard to handle camera movement and draw mode
		"""
		# get pressed keys
		keypress = pygame.key.get_pressed()

		# randomize world if R is pressed and enough frames have passed since last time
		if keypress[pygame.K_r]:
			if not self.seedWorldTimer:
				self.seedWorldTimer = int(self.FPS/4)
				self.calculateWorldValues()
				self.findPolygons()
		# decrement delay between allowed randomizations
		if self.seedWorldTimer:
			self.seedWorldTimer -= 1

		#change displayMode if necessary
		if keypress[pygame.K_p]:
			self.displayMode = self.DISPLAYMODE_POINTS
			glEnable(GL_CULL_FACE)	#enable culling
			glCullFace(GL_BACK)
		elif keypress[pygame.K_o]:
			self.displayMode = self.DISPLAYMODE_MESH
			glDisable(GL_CULL_FACE)	#disable culling for mesh viewing
		elif keypress[pygame.K_i]:
			self.displayMode = self.DISPLAYMODE_WIREFRAME

		#apply polar camera movement
		if keypress[pygame.K_w]:
			self.cameraPolar[2] -= 0.08 * self.dt
			if self.cameraPolar[2] < 1:
				self.cameraPolar[2] = 1.0
		if keypress[pygame.K_s]:
			self.cameraPolar[2] += 0.08 * self.dt
			if self.cameraPolar[2] > 179:
				self.cameraPolar[2] = 179
		if keypress[pygame.K_d]:
			self.cameraPolar[1] += 0.08 * self.dt
			if self.cameraPolar[1] > 180:
				self.cameraPolar[1] -= 360
		if keypress[pygame.K_a]:
			self.cameraPolar[1] -= 0.08 * self.dt
			if self.cameraPolar[1] <= -180:
				self.cameraPolar[1] += 360
		# update camera cartesian position
		self.polarCameraToCartesian()


	def drawScene(self):
		"""
		Renders scene in OpenGL. The main axes and bounding box of the world are always drawn,
		but the visualization of the world data depends on the current drawing mode selected
		by the user
		"""
		glBegin(GL_LINES)
		# draw axes
		glColor3f(1, 0, 0)
		glVertex3f(0, 0, 0)
		glVertex3f(self.worldSize/2, 0, 0)
		glColor3f(0, 1, 0)
		glVertex3f(0, 0, 0)
		glVertex3f(0, self.worldSize/2, 0)
		glColor3f(0, 0, 1)
		glVertex3f(0, 0, 0)
		glVertex3f(0, 0, self.worldSize/2)
		# draw bounding box
		glColor3f(1,1,1)
		scalar = (self.worldSize-1)/2
		for x in [-1, 1]:
			for y in [-1,1]:
				for z in [-1,1]:
					glVertex3f(scalar*x, scalar*y, scalar*z)
		for z in [-1, 1]:
			for x in [-1,1]:
				for y in [-1,1]:
					glVertex3f(scalar*x, scalar*y, scalar*z)
		for y in [-1, 1]:
			for z in [-1,1]:
				for x in [-1,1]:
					glVertex3f(scalar*x, scalar*y, scalar*z)
		glEnd()
		# draw spheres if in POINTS mode
		if self.displayMode is self.DISPLAYMODE_POINTS:
			prev = (0, 0, 0)
			offset = int(self.worldSize/2)
			for x in range(self.worldSize):
				for y in range(self.worldSize):
					for z in range(self.worldSize):
						glTranslatef(x-offset-prev[0], y-offset-prev[1], z-offset-prev[2])
						# use threshold for black/white coloring
						if self.world[x][y][z] > self.worldThreshold:
							glColor3f(1, 1, 1)
						else:
							glColor3f(0, 0, 0)
						gluSphere(self.sphere, 0.1, 8, 4)
						prev = (x-offset,y-offset,z-offset)
		# draw mesh if in MESH mode 
		elif self.displayMode is self.DISPLAYMODE_MESH:
			offset = int(self.worldSize/2)
			for x in range(self.worldSize-1):
				for y in range(self.worldSize-1):
					for z in range(self.worldSize-1):
						if self.polygons[x][y][z]:
							glBegin(GL_POLYGON)
							glColor3f(x/self.worldSize,y/self.worldSize,z/self.worldSize)
							for vertex in self.polygons[x][y][z]:
								glVertex3f(x+vertex[0] - offset, y+vertex[1] - offset, z+vertex[2] - offset)
							glEnd()
		# draw wireframe in in WIRE mode
		elif self.displayMode is self.DISPLAYMODE_WIREFRAME:
			offset = int(self.worldSize/2)
			for x in range(self.worldSize-1):
				for y in range(self.worldSize-1):
					for z in range(self.worldSize-1):
						glBegin(GL_LINES)
						glColor3f(x/self.worldSize,y/self.worldSize,z/self.worldSize)
						for vertex in self.polygons[x][y][z]:
							glVertex3f(x+vertex[0] - offset, y+vertex[1] - offset, z+vertex[2] - offset)
						glEnd()
		# draw background in the distance
		glLoadIdentity()
		glBegin(GL_QUADS)
		glColor3f(59/256, 102/256, 212/256)
		glVertex3f(-30, -23, -49.5)
		glVertex3f(30, -23, -49.5)
		glColor3f(184/256, 201/256, 242/256)
		glVertex3f(30, 23, -49.5)
		glVertex3f(-30, 23, -49.5)
		glEnd()
		# HUD in white
		glColor3f(1,1,1)
		# lower left
		glWindowPos2f(10, 10)
		for ch in 'WASD: Rotate':
			glutBitmapCharacter(GLUT_BITMAP_9_BY_15, ord(ch))
		glWindowPos2f(10, 25)
		for ch in 'Wheel: Thresh':
			glutBitmapCharacter(GLUT_BITMAP_9_BY_15, ord(ch))
		glWindowPos2f(10, 40)
		for ch in 'R: Randomize':
			glutBitmapCharacter(GLUT_BITMAP_9_BY_15, ord(ch))
		glWindowPos2f(10, 55)
		for ch in 'O: Object':
			glutBitmapCharacter(GLUT_BITMAP_9_BY_15, ord(ch))
		glWindowPos2f(10, 70)
		for ch in 'I: Wireframe':
			glutBitmapCharacter(GLUT_BITMAP_9_BY_15, ord(ch))
		glWindowPos2f(10, 85)
		for ch in 'P: Points':
			glutBitmapCharacter(GLUT_BITMAP_9_BY_15, ord(ch))
		# upper right
		glWindowPos2f(self.displaySize[0]-118, self.displaySize[1]-25)
		for ch in 'Thresh: %0.2f' % self.worldThreshold:
			glutBitmapCharacter(GLUT_BITMAP_9_BY_15, ord(ch))


	def calculateWorldValues(self):
		"""
		Generate and normalize a new random world using snoise4
		"""
		# use snoise4 to generate a random noise field
		pNoiseSeed = random.random()
		for x in range(self.worldSize):
			for y in range(self.worldSize):
				for z in range(self.worldSize):
					self.world[x][y][z] = snoise4(x/self.worldSize,y/self.worldSize,z/self.worldSize, pNoiseSeed)
		# normalize noise
		worldMax = np.max(self.world)
		worldMin = np.min(self.world)
		for x in range(self.worldSize):
			for y in range(self.worldSize):
				for z in range(self.worldSize):
					self.world[x][y][z] = (self.world[x][y][z] - worldMin) / (worldMax-worldMin)


	def findPolygons(self):
		"""
		Perform MarchingCubesPolygons algorithm across the worldspace to generate an array of polygons to plot
		"""
		#perform marching cubes algorithm
		for x in range(self.worldSize-1):
			for y in range(self.worldSize-1):
				for z in range(self.worldSize-1):
					# format values for entry
					values = [self.world[x][y][z], self.world[x+1][y][z], self.world[x+1][y+1][z], self.world[x][y+1][z],
						self.world[x][y][z+1], self.world[x+1][y][z+1], self.world[x+1][y+1][z+1], self.world[x][y+1][z+1]]
					# perform marchine cubes
					self.polygons[x][y][z] = marchingCubesPolygons(values, self.worldThreshold)






def main():
	# default parameters
	screenWidth=800 
	screenHeight=600
	worldSize = 10
	debug=False
	radius=20
	# check for user command line input
	opts, args = getopt.getopt(sys.argv[1:], 'w:r:d:x:y:h',['worldSize=','viewRadius=','debug=','screenWidth=','screenHeight='])
	for opt,arg in opts:
		if opt in '-h':
			print('')
			print('MarchingCubesVisualizer.py')
			print('  Generates random 3D meshes from simplex noise to display.')
			print('Options:')
			print('  -w, --worldSize <world size to render, must be even> (defaults to 10)')
			print('  -r, --viewRadius <radius for camera to keep from center of world> (defaults to 20)')
			print('  -d, --debug <optional debugger timer report to console> (defaults to false)')
			print('  -x, --screenWidth <screen width in pixels> (defaults to 800')
			print('  -y, --screenHeight <screen height in pixels> (defaults to 600')
			sys.exit()
		elif opt in ('-w','--worldSize'):
			if int(arg) % 2:
				worldSize = int(arg)+1
			else:
				worldSize = int(arg)
		elif opt in ('-r','--viewRadius'):
			radius = int(arg)
		elif opt in ('-d','--debug'):
			if debug is 'True' or 'true':
				debug = True
			elif arg is 'False' or 'false':
				debug = False
			else:
				debug = bool(arg)
		elif opt in ('-x','--screenWidth'):
			screenWidth = int(arg)
		elif opt in ('-y','--screenHeight'):
			screenHeight = int(arg)
	# start app
	App = MarchingCubesVisualizer(screenWidth, screenHeight, worldSize, debug, radius)
	App.mainLoop()




if __name__ == "__main__":
    main()

















