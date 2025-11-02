# shed

A cli tool that acts like an application for your database schemas management using SQLModel orm.

## Installation

Using uv:

    uv tool install https://github.com/gh-PonyM/shed.git

Using pipx:

    pipx install git+https://github.com/gh-PonyM/shed.git#main

## Usage

Create a new project inside the projects folder:

    shed init news_agg -o projects -c postgres://user:pw@localhost:5432/db_name --env lab

This will create the following folder structure:

```shell
projects
└── news_agg
    ├── migrations
    │   └── versions
    └── models.py
```

This will create a config file for local and prod databases using sqlite for local and postgres for prod. 
```yaml
development:
  db:
    news_agg:
      connection:
        db_path: news_agg.sqlite
      type: sqlite
projects:
  news_agg:
    db:
      lab:
        connection:
          database: db_name
          host: localhost
          password: pw
          port: 5432
          username: user
        type: postgres
    module: ./projects/news_agg/models.py
```

Then just define your `SQLModel` files as in [models.py](projects/news_agg/models.py).

## Features

- Clone databases from prod to dev
- Running short-commands for alembic like `revision` or `migrate`
- Alembic command wrapper that takes your project and passes the db information to alembic
- Exporting jsonschemas for your models (see [schemas](schemas/news_agg.ScrapeResult.json))

## How it works under the hood

Alembic uses different config files and folders. The first entrypoint is the `alembic.ini` file and the top of the config 
template we use is this:

```ini
[alembic]
script_location = {script_dir}
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = sqlite:///:memory:
version_locations = {versions_dir}
```

As you can see, the folder containing the version python files can be specified as well as the script location 
where `env.py` and `script.py.mako` is expected to be found. Using a generated `alembic.ini`, `env.py` and `script.py.mako`,
we have less to think of as developer / data engineer.
