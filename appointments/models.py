from django.db import models

class Service(models.Model):
  service_id = models.AutoField(primary_key=True)
  service_name = models.CharField(max_length=100)
  description = models.TextField()
  price = models.DecimalField(max_digits=10, decimal_places=2)
  duration = models.IntegerField()

  def __str__(self):
    return self.service_name

class Hairdresser(models.Model):
  hairdresser_id = models.AutoField(primary_key=True)
  first_name = models.CharField(max_length=50)
  last_name = models.CharField(max_length=50)

  def __str__(self):
    return f"{self.first_name} {self.last_name}"

class Appointment(models.Model):
  appointment_id = models.AutoField(primary_key=True)
  hairdresser = models.ForeignKey(Hairdresser, on_delete=models.CASCADE)
  service = models.ForeignKey(Service, on_delete=models.CASCADE)
  start_datetime = models.DateTimeField()
  end_datetime = models.DateTimeField()
  customer_name = models.TextField()

  def __str__(self):
    return f"{self.service.service} with {self.hairdresser} on {self.start_date}"
