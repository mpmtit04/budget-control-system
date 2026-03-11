{% extends "base.html" %}

{% block content %}

<h2>Budget Dashboard</h2>

<table class="table">

<tr>
<th>Department</th>
<th>Project</th>
<th>Budget</th>
<th>Used</th>
</tr>

{% for b in budgets %}

<tr>
<td>{{b.department}}</td>
<td>{{b.project}}</td>
<td>{{b.amount}}</td>
<td>{{b.used}}</td>
</tr>

{% endfor %}

</table>

{% endblock %}