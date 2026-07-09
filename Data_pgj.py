import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

df = pd.read_csv("carpetasFGJ_acumulado_2025_01.csv", low_memory=False)
df_filtrado = df[df["anio_hecho"].isin([2023, 2024, 2025])]
#print(df.head(5))
#print(df.columns)
#print(df_filtrado.info())
df_filtrado_total = len(df_filtrado)
print(f"Total de registros:  {df_filtrado_total}")

# region Filtro
"""
df_filtrado = df[df['anio_inicio'].isin([2024, 2025])]
df_ordenado = df.sort_values(by='anio_hecho', ascending=False)
años_unicos = sorted(df_filtrado['anio_inicio'].unique(), reverse=True)
delitos_unicos = sorted(df_filtrado['categoria_delito'].unique(), reverse=True)
"""
# endregion

# region duplicados
"""
datos_duplicados = df_filtrado.duplicated().sum()
print(f"datos duplicados: {datos_duplicados}")
"""
# endregion

# region Grafica
# delitos_alcaldia_catalogo = df["alcaldia_catalogo"].value_counts()
"""
delitos_alcaldia_hecho = df["alcaldia_hecho"].value_counts()

# 2. Configurar el lienzo para tener 1 fila y 2 columnas de gráficas
fig, axes = plt.subplots(figsize=(12, 6))
sns.barplot(
    x=delitos_alcaldia_hecho.values, 
    y=delitos_alcaldia_hecho.index, 
    ax=axes, 
    palette="magma"
)
axes.set_title("Delitos por Alcaldía Hecho")
axes.set_xlabel("Número de Carpetas")
axes.set_ylabel("")

#plt.tight_layout()
#plt.show()
"""
# endregion

# region tabla dinamica
"""
tabla = pd.crosstab(
    df_filtrado["categoria_delito"], 
    df_filtrado["anio_hecho"],
    margins=True,
    margins_name="Total"
    )

tabla["% Del total"] = (tabla["Total"] / tabla.loc["Total", "Total"] * 100).round(2)
print(tabla)
"""
# endregion

# region análisis y limpieza de datos

# registros con nulos y ceros
coord_nula = df_filtrado["latitud"].isna() | df_filtrado["longitud"].isna()
coord_con_ceros = (df_filtrado["latitud"] == 0) | (df_filtrado["longitud"] == 0)


# rangos_fuera_de_cdmx
lat_min, lat_max = 19.0, 19.6
long_min, long_max = -99.4, -98.9

# defino para quedarme solo con datos validos, no nulos y sin coordenadas
fuera_cdmx = (
    (df_filtrado["latitud"] < lat_min) | (df_filtrado["latitud"] > lat_max) |
    (df_filtrado["longitud"] < long_min) | (df_filtrado["longitud"] > long_max)
    )

basura = coord_nula | coord_con_ceros | fuera_cdmx
# El ~ es el operador NOT (negación). Le da la vuelta a una máscara: cada True se vuelve False y cada False se vuelve True.
coord_valida = ~basura
total_descarte = basura.sum()
porcentaje_descartado = (total_descarte/df_filtrado_total) * 100

print(f"Total de registros:            {df_filtrado_total}")
print(f"Cordenadas nulas:              {coord_nula.sum()}")
print(f"Cordenadas con ceros:          {coord_con_ceros.sum()}")
print(f"Cordenadas Fuera del bounding: {fuera_cdmx.sum()}")
print(f"Registros descartados:         {total_descarte}")
print(f"Registros validos:             {coord_valida.sum()}")
print(f"% de descarte geoespacial: {porcentaje_descartado:.2f}%")

#endregion