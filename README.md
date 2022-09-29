# Python File Specifications

### What problem is this library trying to solve?

- Some applications are working with plenty data files of all sorts, e.g. CSV,
  JSON lines, fixed-width fields, Excel, etc.. Mostly table-like data.
- Each of these file types has a different schema (fields)
- The schematas may evolve over the lifetime of the application. There are
  different solutions to this problem: provide a migration script, provide
  default values when accessing old data, etc.. But as "user" of the data
  you don't want to be bothered with it.
- How to maintain all the information consistently about the dictories,
  filenames, expected schema, approaches on how to access the data
  within these files, etc.? Something like a registry is needed.


### Approach

- In this library the registry consists of file-specifications grouped
  in an arbitrary user-directory (outside of this package)
- Every file-specification is a small python script (module)
- Because they are files, the specifications can be protected and
  managed in a github repository. Which has many benefits:
  - User's can maintain the filespecs independently
  - It's fully traceable who made what change
  - Leverage git-branches for different filespecs for dev, test and
    production environments
  - No database needed


E.g.
```
  /user/my_app/config/file_specifications
    |- hr_data.py
    |- products.py
    |- customer-until-2019-02.py
    |- customer.py
```

Data-files can now be accessed like:
```
repo = FileSpec.repository("/user/my_app/config/file_specifications")
hr_data = repo.open("/data/hr/hr-data-2019-04.xlsx")
customer_data = repo.open("/data/customer/customer-export-2019-04.csv")
```

The repository will determine which file-spec to apply, and provide
more or less consistent access to the data with these files.

The [Jupyter notebook](url) has a number of examples
