"""Framework LoRa — interface única (Gerência Serial, Cliente, Link budget, Time on Air,
Site survey e Caracterização de antena).

Uso:  python app_framework_lora.py
"""
import sys

from framework_lora.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
