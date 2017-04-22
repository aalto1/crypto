import math
'''
def get_text(name):
   return "lorem ipsum, {} dolor sit amet".format(name)

def p_decorate(func):
   def func_wrapper(name):
       return "<p>{}</p>".format(func(name))
   return func_wrapper

my_get_text = p_decorate(get_text)

print get_text("John")
print my_get_text("John")

# <p>Outputs lorem ipsum, John dolor sit amet</p>
'''

def approxLog(x):
    if x <= 2:
        print 1
        return 0
    print x
    return 1 + approxLog((x+1)/2)

def logga(b, n ):
    if n <= b:
        return 1
    else:
        return logga(b, n/b)+1






y =  21166
print("Approx:",approxLog(y))
print("logga", logga(2, y))
print math.log(y,2)