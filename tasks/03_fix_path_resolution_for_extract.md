the current project settings file as yaml contains paths that are relative. The models contain helpers as pydantic validator to resolve those. 
For extracting the template, we have to use paths 

Expected usage:

    cd project/news_agg
    # run alembic here
    ...

Path in alembic.ini are also resolved relatively to the cwd. Read core.py and resolve the todos.

- Check no absolute paths are in alembic.ini
- Ensure that multiple sqlite dbs are different sections in the ini (may require to customize __eq__ for db connection)
- Ensure for different postgres db connections we get multiple sections if the db connection string will be different (get_dsn can be used)
- Ensure only one entry for postgres connections if only the schema is different for otherwise same values of the connection

# Testing

- Add tests for the plain rendering of the templates that are not done via cli. Render those template in test to a folder inside tests called 'rendered' so we can track them in git.
- Add different szenarios: 
  - two pg with different schema name
  - two pg, one has no schema_name defined
  - 1 pg and 1 sqlite
  - 2 sqlite
