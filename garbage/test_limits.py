import numpy as np
from memory_profiler import memory_usage
from scipy import linalg

def calcular_autovalores(A):
    print(f"Matriz A tamaño: {A.shape}, dtype={A.dtype}")
    eig = linalg.eigvals(A)
    return eig

# Simulación del uso de memoria
A = np.random.rand(5000, 5000)  # sustituye con ss_sys.A
mem_usage = memory_usage((calcular_autovalores, (A,)))
print("Uso máximo de memoria (MB):", max(mem_usage))