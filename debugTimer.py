import time
		
class debugger : 
	"""
	A simple debug timer for logging the time it takes to complete
	different tasks.
	"""

	def __init__(self) :
		self.times = []
		self.tags = []

	def log(self, tag) :
		"""
		Call debugger.log("tag") to log the amount of time
		since the last call to debugger.log(). The tag string
		is used as the identifier when printing the report and
		can be up to 20 characters long
		"""
		self.times.append(time.perf_counter())
		self.tags.append(tag)

	def report(self) :
		"""
		Prints timing report of all tasks and clears the stored
		lists.
		"""
		print('---------------------------------------------')
		for id in range(1,len(self.times)):
			delta = self.times[id] - self.times[id-1]
			print('{:>20}: {:<7f}'.format(self.tags[id], delta))
		self.times = []
		self.tags = []