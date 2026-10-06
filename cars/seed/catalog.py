"""Model catalogue used by the `seed_demo` command.

Prices are rough 2026 Nigerian market ranges in millions of Naira
(foreign-used and new). `wiki` is the English Wikipedia article whose
photos are used for the listing gallery (see `fetch_car_photos`).
"""

MODELS = [
    # key, brand, model, wiki article, filename keywords, body, engine, years, price (₦m), seats, drivetrains, trims, count
    dict(key='corolla', brand='Toyota', model='Corolla', wiki='Toyota Corolla (E210)', kw=['corolla'], body='sedan', engine='petrol_gas',
         years=(2019, 2024), price=(14, 28), seats=5, drive=['fwd'], trims=['LE', 'SE', 'XSE', 'L'], count=5),
    dict(key='camry', brand='Toyota', model='Camry', wiki='Toyota Camry (XV70)', kw=['camry'], body='sedan', engine='petrol_gas',
         years=(2018, 2024), price=(22, 45), seats=5, drive=['fwd'], trims=['LE', 'SE', 'XSE V6', 'XLE'], count=6),
    dict(key='rav4', brand='Toyota', model='RAV4', wiki='Toyota RAV4 (XA50)', kw=['rav4'], body='suv', engine='petrol_gas',
         years=(2019, 2024), price=(30, 55), seats=5, drive=['awd', 'fwd'], trims=['LE', 'XLE', 'Adventure', 'Limited'], count=3),
    dict(key='rav4h', brand='Toyota', model='RAV4 Hybrid', wiki='Toyota RAV4 (XA50)', kw=['rav4'], body='suv', engine='hybrid',
         years=(2020, 2024), price=(38, 62), seats=5, drive=['awd'], trims=['XLE', 'XSE', 'Limited'], count=2),
    dict(key='highlander', brand='Toyota', model='Highlander', wiki='Toyota Highlander', kw=['highlander'], body='suv', engine='petrol_gas',
         years=(2020, 2024), price=(55, 95), seats=7, drive=['awd', 'fwd'], trims=['LE', 'XLE', 'Limited', 'Platinum'], count=4),
    dict(key='lc300', brand='Toyota', model='Land Cruiser', wiki='Toyota Land Cruiser (J300)', kw=['land cruiser', 'lc300', 'j300'], body='suv', engine='petrol_gas',
         years=(2022, 2025), price=(250, 400), seats=7, drive=['4wd'], trims=['GX-R', 'VX', 'GR Sport'], count=2),
    dict(key='prado', brand='Toyota', model='Land Cruiser Prado', wiki='Toyota Land Cruiser Prado', kw=['prado'], body='suv', engine='petrol_gas',
         years=(2016, 2023), price=(60, 120), seats=7, drive=['4wd'], trims=['TX', 'TXL', 'VX'], count=3),
    dict(key='hilux', brand='Toyota', model='Hilux', wiki='Toyota Hilux', kw=['hilux'], body='pickup', engine='diesel',
         years=(2018, 2024), price=(35, 70), seats=5, drive=['4wd'], trims=['SR', 'SR5', 'Legend'], count=3),
    dict(key='sienna', brand='Toyota', model='Sienna', wiki='Toyota Sienna', kw=['sienna'], body='van', engine='hybrid',
         years=(2021, 2024), price=(60, 95), seats=8, drive=['fwd', 'awd'], trims=['LE', 'XLE', 'Platinum'], count=2),
    dict(key='venza', brand='Toyota', model='Venza', wiki='Toyota Venza', kw=['venza', 'harrier'], body='suv', engine='hybrid',
         years=(2021, 2024), price=(45, 70), seats=5, drive=['awd'], trims=['LE', 'XLE', 'Limited'], count=2),
    dict(key='prius', brand='Toyota', model='Prius', wiki='Toyota Prius (XW50)', kw=['prius'], body='hatchback', engine='hybrid',
         years=(2016, 2022), price=(15, 28), seats=5, drive=['fwd'], trims=['L Eco', 'LE', 'XLE'], count=2),

    dict(key='rx', brand='Lexus', model='RX 350', wiki='Lexus RX (AL20)', kw=['rx'], body='suv', engine='petrol_gas',
         years=(2016, 2022), price=(45, 95), seats=5, drive=['awd', 'fwd'], trims=['Base', 'F Sport', 'Premium'], count=5),
    dict(key='rxh', brand='Lexus', model='RX 450h', wiki='Lexus RX (AL20)', kw=['rx'], body='suv', engine='hybrid',
         years=(2017, 2022), price=(55, 105), seats=5, drive=['awd'], trims=['Base', 'F Sport'], count=2),
    dict(key='es', brand='Lexus', model='ES 350', wiki='Lexus ES (XZ10)', kw=['es'], body='sedan', engine='petrol_gas',
         years=(2019, 2024), price=(45, 85), seats=5, drive=['fwd'], trims=['Base', 'F Sport', 'Ultra Luxury'], count=3),
    dict(key='gx', brand='Lexus', model='GX 460', wiki='Lexus GX', kw=['gx'], body='suv', engine='petrol_gas',
         years=(2014, 2022), price=(55, 110), seats=7, drive=['4wd'], trims=['Base', 'Premium', 'Luxury'], count=3),
    dict(key='lx', brand='Lexus', model='LX 600', wiki='Lexus LX (J310)', kw=['lx'], body='suv', engine='petrol_gas',
         years=(2022, 2025), price=(280, 420), seats=7, drive=['4wd'], trims=['Premium', 'F Sport', 'Ultra Luxury'], count=2),

    dict(key='accord', brand='Honda', model='Accord', wiki='Honda Accord (tenth generation)', kw=['accord'], body='sedan', engine='petrol_gas',
         years=(2018, 2022), price=(22, 40), seats=5, drive=['fwd'], trims=['LX', 'Sport', 'EX-L', 'Touring'], count=3),
    dict(key='civic', brand='Honda', model='Civic', wiki='Honda Civic (tenth generation)', kw=['civic'], body='sedan', engine='petrol_gas',
         years=(2016, 2021), price=(14, 25), seats=5, drive=['fwd'], trims=['LX', 'EX', 'Sport'], count=2),
    dict(key='crv', brand='Honda', model='CR-V', wiki='Honda CR-V (fifth generation)', kw=['cr-v', 'crv'], body='suv', engine='petrol_gas',
         years=(2017, 2022), price=(25, 45), seats=5, drive=['awd', 'fwd'], trims=['LX', 'EX', 'EX-L', 'Touring'], count=3),
    dict(key='pilot', brand='Honda', model='Pilot', wiki='Honda Pilot', kw=['pilot'], body='suv', engine='petrol_gas',
         years=(2016, 2022), price=(35, 60), seats=8, drive=['awd'], trims=['EX', 'EX-L', 'Touring', 'Elite'], count=2),

    dict(key='c205', brand='Mercedes-Benz', model='C 300', wiki='Mercedes-Benz C-Class (W205)', kw=['c-class', 'w205', 'c 300', 'c300', 'c 200'], body='sedan', engine='petrol_gas',
         years=(2015, 2021), price=(28, 55), seats=5, drive=['rwd'], trims=['Base', 'AMG Line', '4MATIC'], count=3),
    dict(key='c206', brand='Mercedes-Benz', model='C 300 (W206)', wiki='Mercedes-Benz C-Class (W206)', kw=['c-class', 'w206', 'c 300', 'c 200'], body='sedan', engine='petrol_gas',
         years=(2022, 2025), price=(70, 110), seats=5, drive=['rwd', 'awd'], trims=['AMG Line', '4MATIC'], count=2),
    dict(key='e213', brand='Mercedes-Benz', model='E 350', wiki='Mercedes-Benz E-Class (W213)', kw=['e-class', 'w213', 'e 350', 'e 300', 'e 220'], body='sedan', engine='petrol_gas',
         years=(2017, 2023), price=(45, 95), seats=5, drive=['rwd', 'awd'], trims=['Base', 'AMG Line', '4MATIC'], count=2),
    dict(key='gle', brand='Mercedes-Benz', model='GLE 450', wiki='Mercedes-Benz GLE', kw=['gle', 'w167'], body='suv', engine='petrol_gas',
         years=(2020, 2024), price=(95, 170), seats=5, drive=['awd'], trims=['4MATIC', 'AMG Line', 'AMG 53'], count=2),
    dict(key='glc', brand='Mercedes-Benz', model='GLC 300', wiki='Mercedes-Benz GLC', kw=['glc', 'x254'], body='suv', engine='petrol_gas',
         years=(2023, 2025), price=(85, 140), seats=5, drive=['awd', 'rwd'], trims=['Base', '4MATIC', 'AMG Line'], count=3),
    dict(key='gclass', brand='Mercedes-Benz', model='G 63 AMG', wiki='Mercedes-Benz G-Class', kw=['g-class', 'g 63', 'g63', 'g 500', 'w463', 'g-klasse'], body='suv', engine='petrol_gas',
         years=(2019, 2024), price=(280, 450), seats=5, drive=['4wd'], trims=['AMG', 'Night Edition'], count=2),

    dict(key='bmw3', brand='BMW', model='330i', wiki='BMW 3 Series (G20)', kw=['3 series', 'g20', '330', '320'], body='sedan', engine='petrol_gas',
         years=(2019, 2023), price=(45, 80), seats=5, drive=['rwd', 'awd'], trims=['Sport Line', 'M Sport', 'xDrive'], count=2),
    dict(key='x5', brand='BMW', model='X5 xDrive40i', wiki='BMW X5 (G05)', kw=['x5', 'g05'], body='suv', engine='petrol_gas',
         years=(2019, 2024), price=(95, 170), seats=5, drive=['awd'], trims=['xLine', 'M Sport'], count=2),
    dict(key='x3', brand='BMW', model='X3 xDrive30i', wiki='BMW X3 (G01)', kw=['x3', 'g01'], body='suv', engine='petrol_gas',
         years=(2018, 2023), price=(45, 85), seats=5, drive=['awd'], trims=['xLine', 'M Sport'], count=2),

    dict(key='elantra', brand='Hyundai', model='Elantra', wiki='Hyundai Elantra', kw=['elantra', 'avante'], body='sedan', engine='petrol_gas',
         years=(2021, 2024), price=(22, 38), seats=5, drive=['fwd'], trims=['SE', 'SEL', 'Limited'], count=2),
    dict(key='tucson', brand='Hyundai', model='Tucson', wiki='Hyundai Tucson', kw=['tucson'], body='suv', engine='petrol_gas',
         years=(2022, 2025), price=(35, 55), seats=5, drive=['fwd', 'awd'], trims=['SE', 'SEL', 'Limited'], count=2),
    dict(key='santafe', brand='Hyundai', model='Santa Fe', wiki='Hyundai Santa Fe', kw=['santa fe'], body='suv', engine='petrol_gas',
         years=(2024, 2025), price=(70, 95), seats=7, drive=['awd', 'fwd'], trims=['SE', 'SEL', 'Limited'], count=2),
    dict(key='ioniq5', brand='Hyundai', model='Ioniq 5', wiki='Hyundai Ioniq 5', single_generation=True, kw=['ioniq'], body='suv', engine='electric',
         years=(2022, 2024), price=(60, 90), seats=5, drive=['rwd', 'awd'], trims=['SE', 'SEL', 'Limited'], count=2),

    dict(key='sportage', brand='Kia', model='Sportage', wiki='Kia Sportage', kw=['sportage'], body='suv', engine='petrol_gas',
         years=(2022, 2025), price=(35, 55), seats=5, drive=['fwd', 'awd'], trims=['LX', 'EX', 'X-Line'], count=2),
    dict(key='sorento', brand='Kia', model='Sorento', wiki='Kia Sorento', kw=['sorento'], body='suv', engine='petrol_gas',
         years=(2021, 2024), price=(45, 70), seats=7, drive=['awd', 'fwd'], trims=['LX', 'EX', 'SX'], count=2),

    dict(key='explorer', brand='Ford', model='Explorer', wiki='Ford Explorer (sixth generation)', kw=['explorer'], body='suv', engine='petrol_gas',
         years=(2020, 2024), price=(55, 90), seats=7, drive=['awd', 'rwd'], trims=['XLT', 'Limited', 'ST'], count=2),
    dict(key='ranger', brand='Ford', model='Ranger', wiki='Ford Ranger (T6)', kw=['ranger'], body='pickup', engine='diesel',
         years=(2019, 2024), price=(35, 60), seats=5, drive=['4wd'], trims=['XL', 'XLT', 'Wildtrak'], count=2),

    dict(key='p3008', brand='Peugeot', model='3008', wiki='Peugeot 3008', kw=['3008'], body='suv', engine='petrol_gas',
         years=(2018, 2023), price=(25, 45), seats=5, drive=['fwd'], trims=['Active', 'Allure', 'GT Line'], count=2),
    dict(key='altima', brand='Nissan', model='Altima', wiki='Nissan Altima', kw=['altima'], body='sedan', engine='petrol_gas',
         years=(2019, 2023), price=(20, 35), seats=5, drive=['fwd'], trims=['S', 'SV', 'SR'], count=2),

    dict(key='rr', brand='Land Rover', model='Range Rover', wiki='Range Rover (L460)', kw=['range rover', 'l460'], body='suv', engine='petrol_gas',
         years=(2022, 2025), price=(350, 550), seats=5, drive=['4wd'], trims=['SE', 'HSE', 'Autobiography'], count=2),
    dict(key='rrs', brand='Land Rover', model='Range Rover Sport', wiki='Range Rover Sport (L461)', kw=['range rover sport', 'l461'], body='suv', engine='petrol_gas',
         years=(2023, 2025), price=(220, 320), seats=5, drive=['4wd'], trims=['SE', 'Dynamic HSE'], count=1),
    dict(key='velar', brand='Land Rover', model='Range Rover Velar', wiki='Range Rover Velar', kw=['velar'], body='suv', engine='petrol_gas',
         years=(2018, 2023), price=(70, 140), seats=5, drive=['awd'], trims=['S', 'SE', 'R-Dynamic HSE'], count=1),

    dict(key='tiguan', brand='Volkswagen', model='Tiguan', wiki='Volkswagen Tiguan', kw=['tiguan'], body='suv', engine='petrol_gas',
         years=(2018, 2023), price=(25, 45), seats=5, drive=['fwd', 'awd'], trims=['S', 'SE', 'SEL R-Line'], count=1),
    dict(key='model3', brand='Tesla', model='Model 3', wiki='Tesla Model 3', kw=['model 3'], body='sedan', engine='electric',
         years=(2019, 2024), price=(45, 75), seats=5, drive=['rwd', 'awd'], trims=['Standard Range Plus', 'Long Range', 'Performance'], count=2),
    dict(key='modely', brand='Tesla', model='Model Y', wiki='Tesla Model Y', kw=['model y'], body='suv', engine='electric',
         years=(2021, 2024), price=(55, 85), seats=5, drive=['awd'], trims=['Long Range', 'Performance'], count=2),
]

BODY_TYPES = [
    ('sedan', 'Sedan'),
    ('suv', 'SUV'),
    ('hatchback', 'Hatchback'),
    ('pickup', 'Pickup'),
    ('van', 'Minivan'),
    ('coupe', 'Coupe'),
]

COLORS = ['Black', 'White', 'Silver', 'Grey', 'Blue', 'Red', 'Pearl White', 'Midnight Black', 'Champagne', 'Dark Green']

# city, state, weight
LOCATIONS = [
    ('Lekki', 'Lagos', 10), ('Ikeja', 'Lagos', 8), ('Victoria Island', 'Lagos', 5), ('Surulere', 'Lagos', 3),
    ('Wuse II', 'FCT', 6), ('Gwarinpa', 'FCT', 4), ('Port Harcourt', 'Rivers', 5), ('Ibadan', 'Oyo', 3),
    ('Enugu', 'Enugu', 2), ('Benin City', 'Edo', 2), ('Kano', 'Kano', 2), ('Abeokuta', 'Ogun', 1),
]

FEATURES = {
    'Comfort': ['Leather seats', 'Heated seats', 'Ventilated seats', 'Dual-zone climate control', 'Sunroof', 'Panoramic roof',
                'Keyless entry', 'Push-button start', 'Power tailgate', 'Third-row seating'],
    'Technology': ['Apple CarPlay', 'Android Auto', 'Navigation', 'Premium sound system', 'Wireless charging',
                   'Head-up display', 'Digital instrument cluster', 'Bluetooth'],
    'Safety': ['Reverse camera', '360° camera', 'Blind-spot monitoring', 'Lane keep assist', 'Adaptive cruise control',
               'Parking sensors', 'Automatic emergency braking'],
    'Performance': ['Turbocharged engine', 'Sport mode', 'All-terrain modes', 'Tow package', 'Air suspension'],
}
