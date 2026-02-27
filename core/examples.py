# Built-in code examples shown in the "Examples" dropdown menu.
# Each entry is a dict with 'title' (menu label) and 'code' (Python source).

EXAMPLES = [
    {
        "title": "Recursion — Factorial",
        "code": (
            "def factorial(n):\n"
            "    if n == 0:\n"
            "        return 1\n"
            "    return n * factorial(n - 1)\n"
            "\n"
            "result = factorial(5)\n"
            "print('5! =', result)\n"
        ),
    },
    {
        "title": "Recursion — Fibonacci",
        "code": (
            "def fib(n):\n"
            "    if n <= 1:\n"
            "        return n\n"
            "    return fib(n - 1) + fib(n - 2)\n"
            "\n"
            "for i in range(8):\n"
            "    print(f'fib({i}) = {fib(i)}')\n"
        ),
    },
    {
        "title": "Sorting — Bubble Sort",
        "code": (
            "def bubble_sort(arr):\n"
            "    n = len(arr)\n"
            "    for i in range(n):\n"
            "        for j in range(0, n - i - 1):\n"
            "            if arr[j] > arr[j + 1]:\n"
            "                arr[j], arr[j + 1] = arr[j + 1], arr[j]\n"
            "\n"
            "nums = [64, 34, 25, 12, 22, 11, 90]\n"
            "bubble_sort(nums)\n"
            "print('Sorted:', nums)\n"
        ),
    },
    {
        "title": "Class & Object — Inheritance",
        "code": (
            "class Animal:\n"
            "    def __init__(self, name):\n"
            "        self.name = name\n"
            "\n"
            "    def speak(self):\n"
            "        return 'Some sound'\n"
            "\n"
            "class Dog(Animal):\n"
            "    def speak(self):\n"
            "        return 'Woof!'\n"
            "\n"
            "class Cat(Animal):\n"
            "    def speak(self):\n"
            "        return 'Meow!'\n"
            "\n"
            "animals = [Dog('Rex'), Cat('Whiskers'), Dog('Buddy')]\n"
            "for a in animals:\n"
            "    print(f'{a.name} says: {a.speak()}')\n"
        ),
    },
    {
        "title": "List Comprehension",
        "code": (
            "numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\n"
            "\n"
            "evens = [x for x in numbers if x % 2 == 0]\n"
            "squares = [x ** 2 for x in numbers]\n"
            "even_squares = [x ** 2 for x in numbers if x % 2 == 0]\n"
            "\n"
            "print('Evens:', evens)\n"
            "print('Squares:', squares)\n"
            "print('Even squares:', even_squares)\n"
        ),
    },
]
