from django.db import migrations

INCOME = [
    ("helb", "HELB", False, "helb,loan,disbursement,higher education loans board"),
    ("parents", "Parents / guardian", False, "mum,mom,dad,mother,father,parent,parents,guardian,upkeep,allowance,pocket money"),
    ("side-hustle", "Side hustle", False, "hustle,gig,freelance,client,commission,tutoring,payment for"),
    ("scholarship", "Scholarship / bursary", False, "scholarship,bursary,cdf,grant,sponsor"),
    ("other-income", "Other income", False, ""),
]

EXPENSE = [
    ("food", "Food", True, "food,lunch,supper,dinner,breakfast,kibanda,vibandaski,chapati,githeri,mandazi,naivas,quickmart,carrefour,supermarket,groceries,cafeteria,mess,restaurant,hotel,chips,tea,milk,bread,ugali,sukuma"),
    ("accommodation", "Accommodation", True, "rent,hostel,room,landlord,caretaker,accommodation,deposit,bedsitter"),
    ("transport", "Transport", True, "matatu,fare,bus,boda,bodaboda,uber,bolt,little,taxi,transport,fuel,sgr,train"),
    ("education", "Education", True, "printing,photocopy,stationery,books,textbook,fees,exam,clearance,library,notes,pen,course,tuition"),
    ("internet", "Internet & airtime", True, "data,bundles,airtime,safaricom,airtel,telkom,wifi,internet,faiba,zuku"),
    ("personal", "Personal care", False, "toiletries,soap,lotion,salon,barber,haircut,clothes,shoes,laundry,pharmacy,chemist"),
    ("entertainment", "Entertainment", False, "party,club,movie,cinema,netflix,showmax,spotify,concert,outing,drinks,games,betting,bet,sportpesa,odibets"),
    ("other-expense", "Other", False, ""),
]


def create(apps, schema_editor):
    Category = apps.get_model("transactions", "Category")
    for kind, rows in (("income", INCOME), ("expense", EXPENSE)):
        for slug, name, essential, keywords in rows:
            Category.objects.update_or_create(
                owner=None, kind=kind, slug=slug,
                defaults={"name": name, "is_essential": essential, "keywords": keywords},
            )


def remove(apps, schema_editor):
    Category = apps.get_model("transactions", "Category")
    Category.objects.filter(owner__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("transactions", "0001_initial")]
    operations = [migrations.RunPython(create, remove)]
