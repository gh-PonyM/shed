Context

This tool has templates for env.py and pyscript.make. I want to add an option to the init command and revision command 
to actually render the templates and store them inside the directory where alembic needs to have it. 
One challenge is that the paths should be again relative. When using the options, point the user that he should from now on 
use the raw alembic tool for managing migrations. It is also useful to later update extracted templates again when new versions of the tool 
are released. 

# How to implement

- Find a good name for the flag `--option` (breakout? extrude? or what is commonly used for such an operation?)
- Write a new short test using the sqlite migration.
- At this point, we convert the templates to Jinja2 templates to accomplish the new needs.
- Since the settings specifies different db urls and schemas, we want to have templates that can mirror this for normal alembic usage.

The cookbook in the docs lists such a scenario:

> Long before Alembic had the “multiple bases” feature described in Working with Multiple Bases, 
> projects had a need to maintain more than one Alembic version history in a single project, 
> where these version histories are completely independent of each other and each refer
> to their own alembic_version table, either across multiple databases, schemas, or namespaces. 
> A simple approach was added to support this, the --name flag on the commandline. 
> This flag allows named sections within the alembic.ini file to be present 
> (but note it does not apply to pyproject.toml configuration, where only the [tool.alembic] 
> section is used). First, one would create an alembic.ini file of this form:

```ini
[DEFAULT]
# all defaults shared between environments go here

sqlalchemy.url = postgresql://scott:tiger@hostname/mydatabase

[schema1]
# path to env.py and migration scripts for schema1
script_location = myproject/revisions/schema1

[schema2]
# path to env.py and migration scripts for schema2
script_location = myproject/revisions/schema2

[schema3]
# path to env.py and migration scripts for schema3
script_location = myproject/revisions/db2

# this schema uses a different database URL as well
sqlalchemy.url = postgresql://scott:tiger@hostname/myotherdatabase
```
and this is then be used with:

    uv run alembic --name schema2 revision -m "new rev for schema 2" --autogenerate

Different environment would translate to different projects that we have.

## env.py changes

- use `current_tenant = context.get_x_argument(as_dictionary=True).get("tenant")` instead of env vars
  - alembic command changes then to `alembic -x tenant=some_schema revision -m "rev1" --autogenerate`

