# ---------------------------------------------------------------------------
# Employee name registry
# ---------------------------------------------------------------------------
# Maps the short display name stored in the fingerprint machine → full name.
#
# To add a new employee, append one line:
#   'NamaFingerprint': 'Nama Lengkap',
#
# Matching is exact (case-sensitive) and mirrors whatever the fingerprint
# machine stores in the Nama column of the scanlog.
# If a scanlog name is not found here the raw fingerprint name is used as-is.
# ---------------------------------------------------------------------------

NAMA_LENGKAP: dict[str, str] = {
    'Abida':   'Abida Rahmi',
    'Dhalail': 'Achmad Dhalail Fauzi',
    'Anshori': 'Anshori',
    'Arif':    'Arif Adi Nugroho',
    'Danta':   'Danta Putra Perdana',
    'Rani':    'Diah Rani Prahasti',
    'Didin':   'Didin Mathias',
    'Faizal':  'Faizal Prasetyo Adi',
    'Fitri':   'Fitriansyah',
    'Hermanto':'Hermanto Pribadi',
    'Marto':   'Marto',
    'Ahmad':   'Muhammad Nur',
    'Nana':    'Nana Choiril Ummah',
    'Rina':    'Rina Maya Sugiarti',
    'Umie':    'Rumiah Rais',
    'Siti':    'Siti Masriyah',
    'Suli':    'Suliono',
    'Sumari':  'Sumari',
    'Supri':   'Supriyadi',
    'Fai':     'Usman Rifai',
    'Tyo':     'Yanto Sulistyo',
    'Reni':    'Yuniza Nidya Anggreini',
    'puspa':   'Tri Cahyo Puspaningrum',
    'Ola':     'Dayang Aulia Maulidha',
    'marto':   'Marto',
    'purnama': 'Purnama Sancang',
    'basori':  'Basori',
    'rifky':   'Justia Rifki Krismantara',
    'dimaz':   'Dimaz Bagus Ramjana',
    'jemmy':   'Jemmy',
    'inur':    'Yulian Nur Rahman',
    'vika':    'Satvika Ruri',
    'anisa':   'Anisa Nur Rahayu',
    'misran':  'Misran',
    'bayu':    'Bayu Prastyo',
    'wulan':   'Wulan Cahyani Fitri',
    'anis':    'Anis Silvi Yuniaherwanti',
    'diva':    'Salwa Sadiva Putri Ashilla',
    'Joko':    'Joko Catur Setiono',
    'Yuli':    'Yuliansyah',
    'sunoko':  'Sunoko',
}

EMPLOYEE_TYPES: dict[str, str] = {
    'Bayu Prastyo':     'keamanan_malam',
    'Marto':            'keamanan_malam',
    'Purnama Sancang':  'keamanan_malam',
    'Yulian Nur Rahman':'keamanan',
}

DENDA_PER_MENIT: dict[str, float] = {
    'Abida Rahmi':                568.9484126984128,
    'Achmad Dhalail Fauzi':       506.94444444444446,
    'Anis Silvi Yuniaherwanti':   490.9350198412698,
    'Anisa Nur Rahayu':           551.6369047619047,
    'Anshori':                    518.0555555555555,
    'Arif Adi Nugroho':           1314.484126984127,
    'Basori':                     396.8253968253968,
    'Bayu Prastyo':               396.8253968253968,
    'Danta Putra Perdana':        583.0357142857142,
    'Dayang Aulia Maulidha':      490.9350198412698,
    'Diah Rani Prahasti':         594.4444444444445,
    'Didin Mathias':              620.5357142857142,
    'Dimaz Bagus Ramjana':        490.9350198412698,
    'Faizal Prasetyo Adi':        554.2410714285713,
    'Fitriansyah':                611.2103174603175,
    'Hermanto Pribadi':           931.0515873015872,
    'Jemmy':                      546.8521825396825,
    'Justia Rifki Krismantara':   490.9350198412698,
    'Marto':                      396.8253968253968,
    'Misran':                     396.8253968253968,
    'Muhammad Nur':               428.57142857142856,
    'Nana Choiril Ummah':         611.2103174603175,
    'Purnama Sancang':            396.8253968253968,
    'Rina Maya Sugiarti':         672.4206349206348,
    'Rumiah Rais':                725.8928571428571,
    'Salwa Sadiva Putri Ashilla': 396.8253968253968,
    'Siti Masriyah':              864.0873015873016,
    'Suliono':                    458.5317460317461,
    'Sumari':                     650.3968253968254,
    'Supriyadi':                  587.5,
    'Tri Cahyo Puspaningrum':     557.7380952380953,
    'Usman Rifai':                537.8968253968254,
    'Wulan Cahyani Fitri':        490.9350198412698,
    'Yanto Sulistyo':             776.6865079365078,
    'Yulian Nur Rahman':          396.8253968253968,
    'Yuniza Nidya Anggreini':     640.9722222222223,
}
