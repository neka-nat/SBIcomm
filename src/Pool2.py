import multiprocessing
from multiprocessing import Process, Pipe  
from itertools import izip  

class Pool2:
    N_MAX_PIPE = 300
    def __init__(self, proc_num=multiprocessing.cpu_count()):
        self.proc_num = proc_num
    def spawn(self, f):
        def fun(pipe,x):
            pipe.send(f(x))
            pipe.close()
        return fun

    def map(self, f, X):
        outputList = []
        numCalc = len(X)
        pipeCnt = 0
        while pipeCnt < numCalc:
            endPipeNum = min(pipeCnt+self.N_MAX_PIPE, numCalc)
            pipe=[Pipe() for x in X[pipeCnt:endPipeNum]]
            processes=[Process(target=self.spawn(f),args=(c,x)) for x,(p,c) in izip(X[pipeCnt:endPipeNum],pipe)]  
            numProcesses = len(processes)  
            processNum = 0  
            while processNum < numProcesses:  
                endProcessNum = min(processNum+self.proc_num, numProcesses)
                [proc.start() for proc in processes[processNum:endProcessNum]]
                [proc.join() for proc in processes[processNum:endProcessNum]]
                [outputList.append(proc.recv()) for proc, c in pipe[processNum:endProcessNum]]
                processNum = endProcessNum
            [p.close() for p, c in pipe]
            pipeCnt = endPipeNum
        return outputList

if __name__ == '__main__':
    from functools import partial
    p = Pool2(30)
    print p.map(lambda x: x*x, range(2000))
