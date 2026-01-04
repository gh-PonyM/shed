# shed

Are you doing some ETL project, you don't want to manage your database schema with **raw SQL**, and maybe validate 
data from external tools using those schemas e.g. when using LLM output? Then this tool might help you.

`shed` is a cli tool that acts like an application for your database schemas management using `SQLModel` orm and manages 
them for you using `alembic`. You get free json-schema export for all your `pydantic.BaselModel` (**v2**). 

## Use Cases

- You can create your database models git repo that only manages db models, using `shed` to manage db and schemas
- You can add `shed` as tool into an existing python project and add migration files to it, following the folder structure proposed below.

## Installation

Using uv:

    uv tool install https://github.com/gh-PonyM/shed.git

Using pipx:

    pipx install git+https://github.com/gh-PonyM/shed.git#main

## Features

- Clone databases from prod to dev
- Running short-commands for alembic like `revision` or `migrate`
- Alembic command wrapper that takes your project and passes the db information to alembic
- Exporting jsonschemas for your models (see [schemas](schemas/news_agg.ScrapeResult.json))
- Export alembic templates used by the tool with `shed revision --extract`

## Usage

Create a new project inside the projects folder:

    shed init news_agg -o projects -c postgres://user:pw@localhost:5432/db_name --env lab

Or using a sqlite database:

    shed init news_agg -o projects -c sqlite:///news-lab.sqlite --env lab

    # Create a revision for the lab environment
    shed revision news_agg.lab

    # Create a revision for the development database
    # (automatically uses the 'news_agg' database, or any db named 'dev*' or '*dev')
    shed revision news_agg

Emit raw sql using wrapped `alembic` command:

    shed alembic news_agg.lab upgrade head --sql

This will create the following folder structure:

```shell
projects
└── news_agg
    ├── migrations
    │   └── versions
    └── models.py
```

The command using a postgres dns will produce this config file: 

```yaml
projects:
  news_agg:
    db:
      # Development database (auto-created with sqlite)
      news_agg:
        connection:
          # Path relative to the config file
          db_path: news_agg.sqlite
        type: sqlite
      # Production database (from the --env lab option)
      lab:
        connection:
          database: db_name
          host: localhost
          password: pw
          port: 5432
          username: user
          schema_name: public
        type: postgres
    module: projects/news_agg/models.py
```

Then just define your `SQLModel` files as in [models.py](projects/news_agg/models.py).

### Development Database Auto-Detection

When you specify only a project name (e.g., `shed migrate news_agg`), shed automatically detects the development database by:

1. First looking for a database with the same name as the project (e.g., `news_agg`)
2. If not found, searching for databases matching `dev*` or `*dev` patterns
3. Using that database if exactly one match is found
4. Raising an error if no matches or multiple matches are found (asking you to specify the environment explicitly)

This means you can quickly work with your development database without specifying the environment each time.

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
we have hassle creating those files for every project we need to manage data as developer / data engineer.
