right now, on shed init, the environment for dev is called the same as the project. This should be changed to dev. 
the parser for project target used in cli can get rid off checking for the project name itself. 

Validation with command:

    uv run alembic --name schema2 revision -m "new rev for schema 2" --autogenerate
