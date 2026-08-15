-- db/schema/04-create-graph.sql
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
SELECT create_graph('companyx_graph');