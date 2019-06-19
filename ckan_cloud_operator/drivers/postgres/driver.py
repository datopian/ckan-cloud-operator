import psycopg2
import contextlib
import traceback

from ckan_cloud_operator import logs


@contextlib.contextmanager
def connect(*args, **kwargs):
    with psycopg2.connect(*args, **kwargs) as conn:
        yield conn


def create_base_db(admin_conn, db_name, db_password, grant_to_user=None):
    db_info = get_db_role_info(admin_conn, db_name)
    errors = []
    if db_info.get('role'):
        logs.info(f'Role already exists: {db_name}')
        errors.append('role-exists')
    else:
        create_role_if_not_exists(admin_conn, db_name, db_password)
    if db_info.get('db'):
        logs.info(f'DB already exists: {db_name}')
        errors.append('db-exists')
    else:
        logs.info(f'Creating DB: {db_name}')
        _set_session_autocommit(admin_conn)
        with admin_conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{db_name}";')
        _unset_session_autocommit(admin_conn)
    if grant_to_user:
        _set_session_autocommit(admin_conn)
        with admin_conn.cursor() as cur:
            cur.execute(f'GRANT "{db_name}" to "{grant_to_user}";')
        _unset_session_autocommit(admin_conn)

    return errors


def create_role_if_not_exists(admin_conn, role_name, role_password):
    roles = list(list_roles(admin_conn, role_name=role_name))
    if len(roles) == 0:
        logs.info(f'Creating role: {role_name}')
        _set_session_autocommit(admin_conn)
        with admin_conn.cursor() as cur:
            cur.execute(f'CREATE ROLE "{role_name}" WITH LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE;',
                        (role_password,))
            cur.execute(f'GRANT "{role_name}" TO postgres;')
        _unset_session_autocommit(admin_conn)


def delete_role(admin_conn, role_name):
    roles = list(list_roles(admin_conn, role_name=role_name))
    if len(roles) > 0:
        logs.info(f'Deleting role: {role_name}')
        _set_session_autocommit(admin_conn)
        with admin_conn.cursor() as cur:
            try:
                cur.execute(f'DROP ROLE "{role_name}"')
            except psycopg2.ProgrammingError:
                traceback.print_exc()
        _unset_session_autocommit(admin_conn)


def delete_base_db(admin_conn, db_name):
    errors = []
    db_info = get_db_role_info(admin_conn, db_name)
    logs.info(f'Revoking connect and terminating all connections db: {db_name}')
    _set_session_autocommit(admin_conn)
    with admin_conn.cursor() as cur:
        try: cur.execute(f'REVOKE CONNECT ON DATABASE "{db_name}" FROM public;')
        except psycopg2.ProgrammingError:
            traceback.print_exc()
    _unset_session_autocommit(admin_conn)
    with admin_conn.cursor() as cur:
        try: cur.execute('SELECT pg_terminate_backend(pg_stat_activity.pid) '
                         'FROM pg_stat_activity '
                         'WHERE pg_stat_activity.datname = %s;', (db_name,))
        except psycopg2.ProgrammingError:
            traceback.print_exc()
    if db_info.get('db'):
        logs.info(f'Deleting db: {db_name}')
        _set_session_autocommit(admin_conn)
        with admin_conn.cursor() as cur:
            try: cur.execute(f'DROP DATABASE "{db_name}"')
            except psycopg2.ProgrammingError:
                traceback.print_exc()
        _unset_session_autocommit(admin_conn)
    else:
        logs.info(f'DB does not exist: {db_name}')
        errors.append('db-does-not-exist')
    if db_info.get('role'):
        logs.info(f'Deleting role: {db_name}')
        _set_session_autocommit(admin_conn)
        with admin_conn.cursor() as cur:
            try:
                cur.execute(f'DROP ROLE "{db_name}"')
            except psycopg2.ProgrammingError:
                traceback.print_exc()
        _unset_session_autocommit(admin_conn)
    else:
        logs.info(f'Role does not exist: {db_name}')
        errors.append('role-does-not-exist')
    return errors


def get_db_role_info(admin_conn, db_name):
    res = {'role': None, 'db': None}
    cur = admin_conn.cursor()
    fields = 'rolname | rolsuper | rolinherit | rolcreaterole | rolcreatedb | rolcanlogin | rolreplication | rolconnlimit | rolpassword | rolvaliduntil | rolbypassrls | rolconfig |  oid'.split(' | ')
    fields_select = ', '.join(fields)
    cur.execute(f'select {fields_select} from pg_roles where rolname=%s', (db_name,))
    row = cur.fetchone()
    res['role'] = dict(zip(fields, row)) if row else None
    fields = 'datname | datdba | encoding | datcollate | datctype | datistemplate | datallowconn | datconnlimit | datlastsysoid | datfrozenxid | datminmxid | dattablespace | datacl'.split(' | ')
    fields_select = ', '.join(fields)
    cur.execute(f'select {fields_select} from pg_database where datname=%s', (db_name,))
    row = cur.fetchone()
    res['db'] = dict(zip(fields, row)) if row else None
    cur.close()
    return res


def list_db_names(admin_conn, full=False, validate=False):
    if validate: full = True
    failures = []
    cur = admin_conn.cursor()
    cur.execute('select datname from pg_database')
    for row in cur:
        db_name = row[0]
        if full:
            data = get_db_role_info(admin_conn, db_name)
            if validate and not (data.get('db') and data.get('role')): failures.append(db_name)
            yield data
        else:
            yield db_name
    if validate and len(failures) > 0: raise Exception(f'Failed to get role for following dbs: {failures}')


def list_roles(admin_conn, full=False, validate=False, role_name=None):
    if validate: full=True
    failures = []
    cur = admin_conn.cursor()
    if role_name is not None:
        where = ' where rolname=%s'
        args = (role_name,)
    else:
        where = ''
        args = ()
    cur.execute(f'select rolname from pg_roles{where}', args)
    for row in cur:
        role_name = row[0]
        if full:
            data = get_db_role_info(admin_conn, role_name)
            if validate and not (data.get('db') and data.get('role')): failures.append(role_name)
            yield data
        else:
            yield role_name
    if validate and len(failures) > 0: raise Exception(f'Failed to get db for following roles: {failures}')


def initialize_extensions(admin_db_conn, extension_names):
    with admin_db_conn.cursor() as cur:
        cur.execute(' '.join([
            f'CREATE EXTENSION IF NOT EXISTS {extension_name};'
            for extension_name in extension_names
        ]))


def _set_session_autocommit(conn):
    conn.commit()
    conn.set_session(autocommit=True)


def _unset_session_autocommit(conn):
    conn.commit()
    conn.set_session(autocommit=False)
