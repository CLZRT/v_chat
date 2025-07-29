import time

from data.main import DataCollector

if __name__ == '__main__':
    collector = DataCollector()
    collector.start()
    time.sleep(70)
    collector.stop()
