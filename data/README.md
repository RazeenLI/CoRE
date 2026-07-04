# RDB schema / sample relational database


## Core Mission

```text
incoming table → match / extend / create table(s)
```

Treat the **complete RDB as the ground truth**, then artificially "degrade/prune/hide" it into an incomplete existing RDB. Then, use the hidden tables/columns/relations as the input of the incoming table to test whether the system can restore the structure to be close to the original complete RDB.

> 把**完整 RDB 当作 ground truth**，然后人为“退化 / 裁剪 / 隐藏”成一个不完整的 existing RDB，再把被隐藏的 table / column / relation 作为 incoming table 输入，测试系统能不能恢复到接近原始完整 RDB 的结构。


## File Structure

```text
data/
├── README.md
├── Chinook/
│   ├── raw/
│   │   ├── Chinook_PostgreSql.sql
│   ├── parsed/
│   │   ├── schema.json
│   │   ├── constraints.json
│   │   ├── tables/
│   │   │   ├── Album.csv
│   │   │   ├── Artist.csv
│   │   │   ├── ...
│   ├── benchmarks/
│   │   ├── case/
│   │   │   ├── existing/
│   │   │   │   ├── schema.json
│   │   │   │   ├── constraints.json
│   │   │   │   ├── tables/
│   │   │   │   │   ├── Album.csv
│   │   │   │   │   ├── Artist.csv
│   │   │   │   │   ├── ...
│   │   │   ├── steps/
│   │   │   │   ├── step/
│   │   │   │   │   ├──schema.json
│   │   │   │   │   ├── table.csv
│   │   │   │   │   ├── expected_decision.json
│   │   │   │   ├── .../
│   │   │   ├── expected/
│   │   │   │   ├── schema.json
│   │   │   │   ├── constraints.json
│   │   │   │   ├── tables/
│   │   │   │   │   ├── Album.csv
│   │   │   │   │   ├── Artist.csv
│   │   │   │   │   ├── ...
```


## Raw Datasets

### Chinook

A classic sample database that supports SQLite, PostgreSQL, MySQL, SQL Server, etc., suitable for demos and testing.

[Original Link](https://github.com/lerocha/chinook-database "lerocha/chinook-database: Sample ...")