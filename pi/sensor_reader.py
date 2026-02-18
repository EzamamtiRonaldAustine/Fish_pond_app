import random
import time

def read_temperature():
    return 20 + random.random() * 10

def read_ph():
    return 6 + random.random() * 2

def main():
    while True:
        temp = read_temperature()
        ph = read_ph()
        print(f"Temp: {temp:.2f}, pH: {ph:.2f}")
        time.sleep(5)

if __name__ == "__main__":
    main()
