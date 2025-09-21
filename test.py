def foo(a, b):
    print(a, b,sep=',')

d = {'a': 1, 'b': 2}
foo(**d)                   # 等同 foo(a=1, b=2)
