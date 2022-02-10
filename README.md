**Development continues in the [api-editor](https://github.com/lars-reimann/api-editor) repository.**

---------------

# library-analyzer

A tool to analyzer client and API code written in Python.

## Usage

```text
usage: python-analyzer [-h] {api,usages,improve} ...

Analyze Python code.

positional arguments:
  {api,usages,improve}
    api                 List the API of a package.
    usages              Find usages of API elements.
    improve             Suggest how to improve an existing API.

optional arguments:
  -h, --help            show this help message and exit
```

### api command

```text
usage: python-analyzer api [-h] -p PACKAGE -o OUT

optional arguments:
  -h, --help            show this help message and exit
  -p PACKAGE, --package PACKAGE
                        The name of the package. It must be installed in the current interpreter.
  -o OUT, --out OUT     Output directory.
```

### usages command

```text
usage: python-analyzer usages [-h] -p PACKAGE -s SRC -t TMP -o OUT

optional arguments:
  -h, --help            show this help message and exit
  -p PACKAGE, --package PACKAGE
                        The name of the package. It must be installed in the current interpreter.
  -s SRC, --src SRC     Directory containing Python code.
  -t TMP, --tmp TMP     Directory where temporary files can be stored (to save progress in case the program crashes).
  -o OUT, --out OUT     Output directory.
```

### improve command

```text
usage: python-analyzer improve [-h] -a API -u USAGES -o OUT [-m MIN]

optional arguments:
  -h, --help            show this help message and exit
  -a API, --api API     File created by the 'api' command.
  -u USAGES, --usages USAGES
                        File created by the 'usages' command.
  -o OUT, --out OUT     Output directory.
  -m MIN, --min MIN     Minimum number of usages required to keep an API element.
```

### Example usage

1. When running this locally with the cloned repository, create a shell with _poetry_:
    ```shell
    poetry shell
    ```n

2. Run the commands described above:
    ```shell
    # Step 1:
    python-analyzer api -p sklearn -o "/Kaggle Analysis/out"

    # Step 2:
    python-analyzer usages -p sklearn -s "/Kaggle Analysis/Kaggle Kernels" -t "/Kaggle Analysis/tmp" -o "/Kaggle Analysis/out"

    # Step 3:
    python-analyzer improve -a "/Kaggle Analysis/out/scikit-learn__sklearn__1.0__api.json" -u "/Kaggle Analysis/out/scikit-learn__sklearn__1.0__usages.json" -o "/Kaggle Analysis/out"
    ```
