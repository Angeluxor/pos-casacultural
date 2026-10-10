import openpyxl
wb = openpyxl.load_workbook('data/Sistema_Ventas_CasaCultural_MASTER.xlsx', read_only=True, data_only=True)
for s in ['Productos', 'Clientes']:
    ws = wb[s]
    rows = list(ws.iter_rows(min_row=2, max_row=3, values_only=True))
    print(s, ':', rows)
