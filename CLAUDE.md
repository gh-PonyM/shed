# CLAUDE.md

The repository should contain the source code in python for a command line tool that can manage database schemas and migrations. The ideas is to have a yaml config file where different databases can be stored for different projects, supporting types for sqlite and postgres databases. The tools should allow to select a python module with database models. It should provide commands that are built-in into alembic as well as some additional ones.

## Use case

As a developer for data pipelines, I want to manage the source code for different data projects in a monorepo. I'd like a tool that helps me manage the orm model and create migrations for them. I also want to be able to test schema migrations from a copy of the databases

## Tooling

uv should be used to manage the project. pytest is used for testing.

## Architecture

A command line cli wrapper around alembic with a custom yaml config file.

## Packages to use

- SQLModel for database models
- alembic for migrations
- typer as cli tool
- pydantic for config validation

The code itself should be a package that can be installed later. it is called shed.

## Development Commands

ruff for linting, pytest for testing. Just add some documentation to the README.md

## Cli commands

The base cli entrypoint should be shed. 

## Cli subcommands

Be able to bootstrap a migrations folder in the current repo.

    shed init

Like alembic, but creating the mako 

Beeing able to run migrations, for example:

    shed migrate <project.<name>> --dry-run

Please add options that are also required by alembic.

Clone command should support the clone from one into another db, only allowing to clone to the same type (postgres, sqlite). Under the hood, it can use linux terminal commands such as pgdump. For sqlite, a copy of the db (if possible, check that it is synced and not locked).

    shed clone <source> <target>

Creatin revisions using alembic:

   shed revision -m "message" --autogenerate

## Proposed settings format

Here is an example of a settings file we want to use, validated by a pydantic model.

```
development:
  db:
    sqlite:
      connection: ...
    # db_name is not necessary here, ask the user to create the db name if it does not exist
    pglocal:
      connection: ...
projects:
  projectA:
    module: <path to python source code containing sqlmodel definitions>
    db:
      # name of the db, ensure no spaces are allowed here in the validation
      staging:
        type: sqlite
        db_name: "name of db"
        connection:
          db_path: <file path>
      prod:
        type: postgres
        db_name: "name of db"
        connection:
          ... please suggest necessary params such as host port etc
```

Make sure the settings class has a save function. Add the settings path as a private variable on initialisation. Now the settings can be saved after modification.

## Features and Requirements

- Every command as a meaningful help message
- Settings are placed at the OS default location, or can be set via env variable
- settings are added to the context of every subcommand
- Provide dry-run option
- The cli tools should be able to load the classes for database from a given module. Figure out a way
- Each subccomand should be tests
- In each test, overwrite the env variable for the settings, create a fixture to create test settings inside a temp dir, and the cli invoked should read the temporary test config as a file
- Use in-memory test sqlite databases while testing

## Notes

- Be aware how alembic works under the hood. Find the most elegant way to configure it. Ideally, I do not have to provide the files that are normally used by alembic:
  - alembic.ini: contains just default configs. If possible reflext that in code or place a temp file with the content and tell alembic command where to find it
  - env.py: Write this script so that the connection if retrieved from the settings, and the correct db is selected when using the alembic wrapper commands. Use sync db drivers.
  - the versions folder should be created inside the same folder as the project module.
- Type Annotations: use python 3.10+ Syntax not using Optional or Dict, but str | None or dict istead of Dict
- Code design: The cli functions should ideally call 1 function. Split functions that write things to the terminal using typer.secho from code that does purely logic