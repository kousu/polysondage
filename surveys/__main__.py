import sys, os

import surveys

print(surveys, surveys.__name__)


def main():
    print("hello", __name__, __file__, sys.argv)
    surveys.App().run()


if __name__ == "__main__":
    main()
