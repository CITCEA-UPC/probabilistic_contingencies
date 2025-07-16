import socket
import json
import time
import sys

def receive_data():
    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Bind the socket to the port
    server_address = ('10.5.17.40', 22000)       # ip local
    print('starting up on {} port {}'.format(*server_address))
    sock.bind(server_address)

    # Listen for incoming connections
    sock.settimeout(5)
    sock.listen(1)
    l=[]

    # Wait for a connection
    print('waiting for a connection')
    connection, client_address = sock.accept()
    try:
        print('connection from', client_address)
        # Receive the data in small chunks and retransmit it
        
        dades_rebudes = b""  # Utilitzem una cadena de bytes

        while True:
            dades = connection.recv(1024)
            dades_rebudes += dades
            if len(dades) < 1024:  # S'ha arribat al final de la transmissió
                #print('rebut')
                connection.sendall(b'done')
                break
        
        if len(dades_rebudes) != 0:
            dades_descodificades = dades_rebudes.decode('utf-8')
            #print(dades_rebudes)
            l.append(eval(dades_descodificades))
            dades_json = json.loads(dades_descodificades)
            print(dades_json)
            #print('\n')
        
        #print(len(data))

    finally:
        print('closing socket')
        sock.close()
        return(dades_json)