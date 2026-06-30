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
│   │   │   ├── Album.json
│   │   │   ├── Artist.json
│   │   │   ├── ...


```

给我一个python file

我把 parsed的路径和output路径作为参数

然后我提供保存的文件夹的名字（比如说case_A_remove_columns这种）

然后我提供要求文件

比如说一个json或者更合适的格式的文件

保存1

我如果要写一个构造数据集的要求的文件用什么格式，什么结构比较好
我会提供 expected rdb要有哪些table，每个tables里面选择哪些columns，每个table的value保存多少
然后基于这个expected rdb，我继续构造existing和incoming table的要求
1. 把什么table 从 expected rdb中删除掉作为incoming table（这个地方由于整个table都被抽走了所以所有的value都被抽走了）（由于relationship也是table所以是一样的
2. 把什么table的哪些columns从 expected rdb中删除掉作为incoming table（这个时候由于这个table只是抽走了部分column，所有value也会提供一个抽取比例，留在existing table的数据就单纯删除抽走的column的value就好）
## Raw Datasets

### Chinook

A classic sample database that supports SQLite, PostgreSQL, MySQL, SQL Server, etc., suitable for demos and testing.

[Original Link](https://github.com/lerocha/chinook-database "lerocha/chinook-database: Sample ...")