CREATE TABLE IF NOT EXISTS public.users
(
    id bigserial NOT NULL,
    login character varying(255) COLLATE pg_catalog."default" NOT NULL,
    password character varying(255) COLLATE pg_catalog."default" NOT NULL,
    authorizataion boolean NOT NULL DEFAULT false,
    telegram_id bigint,
    CONSTRAINT users_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.users
    OWNER to bot;

