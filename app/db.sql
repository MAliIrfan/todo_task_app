-- Table: public.todo

-- DROP TABLE IF EXISTS public.todo;

CREATE TABLE IF NOT EXISTS public.todo
(
    id integer NOT NULL DEFAULT nextval('todo_id_seq'::regclass),
    title character varying COLLATE pg_catalog."default",
    description character varying COLLATE pg_catalog."default",
    priority integer,
    complete boolean,
    file bytea,
    created_at timestamp without time zone DEFAULT now(),
    due_at timestamp without time zone,
    completed_at timestamp without time zone,
    CONSTRAINT todo_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.todo
    OWNER to postgres;