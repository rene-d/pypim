attach database 'pypi.db' as A;
attach database 'pypi_json.db' as M;
.changes on

select count(*) from A.package;
select count(*) from M.package;

--select name from A.package where name not in (select name from A.list_packages);
--select name from A.list_packages where name not in (select name from A.package);

select name from M.package where name not in (select name from A.package);
select name from A.package where name not in (select name from M.package);
