-- ============================================================
-- Soporte Zencillo - Configuración inicial de Supabase
-- Pegar completo en: Supabase > SQL Editor > New query > Run
-- Es seguro ejecutarlo más de una vez.
-- ============================================================

-- ---------- TABLAS ----------
create table if not exists categorias (
  id serial primary key,
  nombre text unique not null,
  orden int default 0
);

create table if not exists snippets (
  id bigserial primary key,
  categoria_id int references categorias(id) on delete cascade,
  titulo text not null,
  contenido text not null,
  sensible boolean default false,   -- true = contiene credenciales (solo lo ve el admin)
  activo boolean default true,
  orden int default 0,
  created_at timestamptz default now(),
  constraint snippets_cat_titulo_uq unique (categoria_id, titulo)
);

create table if not exists enlaces (
  id bigserial primary key,
  tipo text check (tipo in ('manual','video','externo')),
  titulo text not null,
  url text not null,
  activo boolean default true,
  constraint enlaces_tipo_titulo_uq unique (tipo, titulo)
);

create table if not exists escalamientos (
  id serial primary key,
  area text not null,
  responsable text not null,
  constraint escalamientos_area_uq unique (area)
);

-- ---------- CATEGORÍAS ----------
insert into categorias (nombre, orden) values
  ('Tickets', 1), ('Dispositivos', 2), ('Respuestas Rápidas', 3),
  ('Consultas SQL', 4), ('Responder', 5), ('Videos Clientes', 6)
on conflict (nombre) do nothing;

-- ---------- SEGURIDAD (RLS) ----------
-- La clave pública (anon) solo puede LEER. La service_key ignora RLS (la usa el admin).
alter table categorias    enable row level security;
alter table snippets      enable row level security;
alter table enlaces       enable row level security;
alter table escalamientos enable row level security;

drop policy if exists "lectura" on categorias;
drop policy if exists "lectura" on snippets;
drop policy if exists "lectura" on enlaces;
drop policy if exists "lectura" on escalamientos;

create policy "lectura" on categorias    for select using (true);
create policy "lectura" on snippets      for select using (activo and not sensible);
create policy "lectura" on enlaces       for select using (activo);
create policy "lectura" on escalamientos for select using (true);
