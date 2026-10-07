"""
Blynn API: backend general de Blynn (finanzas personales chilenas).

Base de datos (Postgres/Supabase), autenticación propia y, a partir de
la Etapa 3, los datos de cada usuario (gastos, ingresos, categorías,
metas). El escaneo de boletas NO vive aquí: es un servicio aparte
(`boletas-backend`) al que este backend llamará en la Etapa 4. Ver
README.md.
"""
