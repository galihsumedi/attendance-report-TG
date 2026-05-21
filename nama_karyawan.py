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
    'Anis':    'Anis Silvi Yuniaherwanti',
    'Diva':    'Salwa Sadiva Putri Ashilla',
    'Joko':    'Joko Catur Setiono',
    'Yuli':    'Yuliansyah',
    'sunoko':  'Sunoko',
}
