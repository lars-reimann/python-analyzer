# library-analyzer

```text
usage: library-analyzer [-h] {count} ...

Analyze Python code.

positional arguments:
  {count}
    count     Count how often functions are called/parameters are used and with which values.

optional arguments:
  -h, --help  show this help message and exit
```

```shell
poetry shell
library-analyzer api -p sklearn -o "/mnt/d/Kaggle Analysis/out"
library-analyzer usages -p sklearn -s "/mnt/d/Kaggle Analysis/Kaggle Kernels" -t "/mnt/d/Kaggle Analysis/tmp" -o "/mnt/d/Kaggle Analysis/out"
```

Example query on `merged_count`:
```js
Object.values(merged_count.parameters).map(it => Object.values(it).filter(value => value < 1000).length).reduce((a, b) => a + b, 0)
```
