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
        #print 1
        return []
    #print x
    return [x] + approxLog((x+1)/2)

def logga(b, n ):
    if n <= b:
        return 1
    else:
        return logga(b, n/b)+1






#y = 328382322427425755434242323255252323232

totEven = 0

for y in xrange(3, 3283823224274257554):
    even = 0
    odd = 0
    result = approxLog(y)
    for n in result:
        if(n%2==0):
            even +=1
        else:
            odd +=1
    d = len(result)
    #print(d, "even:" + str(even), "odd:" + str(odd), "even:" + str(1.0*even/d), "odd:" + str(1.0*odd/d))
    totEven += 1.0*even/d
    print("Even coefficient:", totEven/y, y)



    #print("logga", logga(2, y))
print math.log(y,2)