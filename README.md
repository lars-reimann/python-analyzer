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
library-analyzer improve -s "D:\Kaggle Kernels" -e "D:\excluded_files.txt" -o "D:\counter"

poetry shell
library-analyzer improve -s "/mnt/d/Kaggle Analysis/Kaggle Kernels" -e "/mnt/d/Kaggle Analysis/excluded_files.txt" -o "/mnt/d/Kaggle Analysis/counter"
```

Example query on `merged_count`:
```js
Object.values(merged_count.parameters).map(it => Object.values(it).filter(value => value < 1000).length).reduce((a, b) => a + b, 0)
```
