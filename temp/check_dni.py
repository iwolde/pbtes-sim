import pandas as pd

tmy = pd.read_csv('TMY.csv')
tmy['time'] = pd.to_datetime(tmy['Fecha/Hora'])
jan = tmy[tmy['time'].dt.month == 1]
jan7 = jan[jan['time'].dt.day <= 7]

print('Full year DNI stats:')
print('  Max:', tmy['dni'].max())
print('  Hours > 900:', (tmy['dni'] > 900).sum())
print('  Hours > 910:', (tmy['dni'] > 910).sum())
print('  Hours > 827:', (tmy['dni'] > 827).sum())
print('  Hours > 551:', (tmy['dni'] > 551).sum())
print()
print('January 1-7 DNI stats:')
print('  Max:', jan7['dni'].max())
print('  Hours > 900:', (jan7['dni'] > 900).sum())
print('  Hours > 910:', (jan7['dni'] > 910).sum())
print('  Hours > 827:', (jan7['dni'] > 827).sum())
print('  Hours > 551:', (jan7['dni'] > 551).sum())
print()
print('DNI values Jan 1-7 where E > 800:')
for _, row in jan7.iterrows():
    if row['dni'] > 800:
        print(f"  {row['time']}: DNI={row['dni']:.0f}")
