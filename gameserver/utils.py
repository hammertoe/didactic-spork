#import random

#class lcg(random.Random):
#    def __init__( self, seed=1 ):
#        self.state = seed

#    def random(self):
#        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
#        return self.state

import random as orig_random

random = orig_random.Random()
random.seed()
