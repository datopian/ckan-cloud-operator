# Infrastructure Management


## DB Connection pooler - PgBouncer

```
psql -d `ckan-cloud-operator db connection-string --admin`
postgres=> \connect pgbouncer
pgbouncer=# show lists;
pgbouncer=# show pools;
pgbouncer=# show help;
```
